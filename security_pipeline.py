#!/usr/bin/env python3
"""
Host-side orchestrator tying together the security_* Django commands
(main/management/commands/security_*.py), fail2ban, and nginx_blocklist.conf
into one pipeline. Supersedes getbadip.py, which shelled out to raw psql
and hardcoded its AbuseIPDB key - all DB/AbuseIPDB work now happens inside
the app container via `docker exec ... manage.py`, which this script only
orchestrates.

Two lists this script cares about, per the intended workflow:
  - the PRODUCTION list: IPs already permanently banned (fail2ban's
    `permanent-ban` jail - the durable, authoritative "already handled"
    set) and IPs already reported to AbuseIPDB by us (tracked in
    security_reported_ips.json, since AbuseIPDB's public API has no
    "reports I filed" endpoint of its own).
  - the BUILD list: fresh candidates from analytics.PageViewLog, minus
    anything already on the production list above - only IPs that are
    genuinely new get an AbuseIPDB score check spent on them, and only
    ones that clear --min-score become the final ban/report list.

Every side effect (filing a report, banning, rewriting the blocklist
seed, restarting the app container) is gated behind --confirm; without
it, this only ever prints what it WOULD do.

Usage:
  python3 security_pipeline.py                      # dry run, full pipeline
  python3 security_pipeline.py --min-score 90 --confirm
  python3 security_pipeline.py --days 14 --confirm
"""
import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _valid_ips(tokens):
    """
    Filters a list of whitespace-split tokens down to ones that actually
    parse as an IP address. fail2ban's "Banned IP list:" output is just
    space-joined text - if a malformed banip call ever gets a multi-word
    string banned as one "IP" (this has happened: a stray
    "fail2ban-client permanent-ban set banip sudo" ended up as five
    literal non-IP entries in this exact jail), whitespace-splitting it
    back apart produces garbage tokens that will blow up anything
    downstream expecting real IPs (e.g. a Postgres ip_address__in query).
    """
    valid = set()
    for token in tokens:
        try:
            ipaddress.ip_address(token)
            valid.add(token)
        except ValueError:
            pass
    return valid

WEB_CONTAINER = os.environ.get("SECURITY_WEB_CONTAINER", "tobuweb-web")
PERMANENT_BAN_JAIL = "permanent-ban"
REPORTED_LOG_PATH = Path(__file__).parent / "security_reported_ips.json"
BLOCK_PERMANENT_SH_PATH = Path(__file__).parent / "block_permanent.sh"


def run(cmd, input_data=None, check=True):
    return subprocess.run(cmd, input=input_data, capture_output=True, text=True, check=check)


def docker_exec_manage(args, input_data=None):
    cmd = ["docker", "exec"]
    if input_data is not None:
        cmd.append("-i")
    cmd += [WEB_CONTAINER, "python", "manage.py"] + args
    result = run(cmd, input_data=input_data)
    return result.stdout


def get_all_banned_ips():
    """Every IP currently banned across every fail2ban jail on this host."""
    banned = set()
    status = run(["fail2ban-client", "status"]).stdout
    match = re.search(r"Jail list:\s+(.*)", status)
    if not match:
        return banned
    for jail in [j.strip() for j in match.group(1).split(",") if j.strip()]:
        jail_status = run(["fail2ban-client", "status", jail], check=False).stdout
        for line in jail_status.splitlines():
            if "Banned IP list:" in line:
                ips = line.split("Banned IP list:")[1].strip()
                if ips:
                    banned.update(_valid_ips(ips.split()))
    return banned


def get_permanent_ban_ips():
    status = run(["fail2ban-client", "status", PERMANENT_BAN_JAIL], check=False).stdout
    for line in status.splitlines():
        if "Banned IP list:" in line:
            ips = line.split("Banned IP list:")[1].strip()
            return _valid_ips(ips.split()) if ips else set()
    return set()


def load_reported_log():
    if REPORTED_LOG_PATH.exists():
        return json.loads(REPORTED_LOG_PATH.read_text())
    return {}


def save_reported_log(log):
    REPORTED_LOG_PATH.write_text(json.dumps(log, indent=2, sort_keys=True))


def ban_ip(ip):
    run(["fail2ban-client", "set", PERMANENT_BAN_JAIL, "banip", ip], check=False)


def regenerate_block_permanent_sh(all_permaban_ips):
    """
    Rewrites block_permanent.sh's IP_LIST from the CURRENT permanent-ban
    jail state, so the script stays an accurate, portable seed for a
    fresh deployment instead of a hand-appended list that drifts stale.
    """
    if not BLOCK_PERMANENT_SH_PATH.exists():
        return
    content = BLOCK_PERMANENT_SH_PATH.read_text()
    ip_lines = "\n".join(f'  "{ip}"' for ip in sorted(all_permaban_ips))
    new_array = f"IP_LIST=(\n{ip_lines}\n)"
    new_content = re.sub(r"IP_LIST=\([^)]*\)", new_array, content, count=1, flags=re.DOTALL)
    BLOCK_PERMANENT_SH_PATH.write_text(new_content)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--days", type=int, default=30, help="Lookback window for the DB scan (default 30)")
    parser.add_argument("--min-score", type=int, default=90,
                         help="Minimum AbuseIPDB score to act on (default 90)")
    parser.add_argument("--confirm", action="store_true",
                         help="Actually file reports, ban IPs, rewrite block_permanent.sh, and "
                              "restart the app container. Without this, everything is dry-run.")
    args = parser.parse_args()

    print(f"[1/6] Loading production state (fail2ban + reported-IP log)...")
    permaban_ips = get_permanent_ban_ips()
    all_banned_ips = get_all_banned_ips()
    reported_log = load_reported_log()
    print(f"      permanent-ban jail: {len(permaban_ips)} IPs")
    print(f"      banned across all jails: {len(all_banned_ips)} IPs")
    print(f"      previously reported to AbuseIPDB: {len(reported_log)} IPs")

    print(f"[2/6] Scanning PageViewLog for candidates (last {args.days} days)...")
    candidates = json.loads(docker_exec_manage(
        ["security_scan", "--no-abuse-check", "--json", "--days", str(args.days)]
    ))
    print(f"      {len(candidates)} raw candidates found")

    print("[3/6] Building the check list (candidates minus production list)...")
    already_handled = permaban_ips | set(reported_log.keys())
    check_list = {c["ip"]: c for c in candidates if c["ip"] not in already_handled}
    skipped_already_banned = sum(1 for c in candidates if c["ip"] in permaban_ips)
    skipped_already_reported = sum(1 for c in candidates if c["ip"] in reported_log)
    print(f"      {len(check_list)} IPs to check "
          f"(skipped {skipped_already_banned} already permabanned, "
          f"{skipped_already_reported} already reported)")

    if not check_list:
        print("Nothing new to check. Done.")
        return

    print(f"[4/6] Checking {len(check_list)} IPs against AbuseIPDB...")
    scores = json.loads(docker_exec_manage(
        ["security_bulk_check", "--json"], input_data=json.dumps(list(check_list.keys()))
    ))

    ban_report = []
    for ip, evidence in check_list.items():
        score_data = scores.get(ip, {})
        score = score_data.get("abuse_score", 0)
        if score >= args.min_score:
            ban_report.append({"ip": ip, "score": score, "evidence": evidence, "score_data": score_data})
    ban_report.sort(key=lambda r: -r["score"])

    print(f"[5/6] {len(ban_report)} IP(s) meet the >= {args.min_score} threshold:")
    for r in ban_report:
        print(f"      {r['ip']:<16} score={r['score']:>3} "
              f"scanner_hits={len(r['evidence']['scanner_hits']):>3} "
              f"sensitive_hits={len(r['evidence']['sensitive_hits']):>2}")

    if not ban_report:
        print("Nothing meets the threshold. Done.")
        return

    if not args.confirm:
        print("\n[DRY RUN] Would file AbuseIPDB reports, permaban, update nginx_blocklist.conf, "
              "and restart the app container for the IPs above. Pass --confirm to actually do it.")
        for r in ban_report:
            evidence_json = json.dumps({
                "scanner_hits": r["evidence"]["scanner_hits"],
                "sensitive_hits": r["evidence"]["sensitive_hits"],
            })
            preview = json.loads(docker_exec_manage(
                ["security_report_auto", "--ip", r["ip"], "--evidence-json", evidence_json]
            ))
            print(f"      {r['ip']}: categories={preview['categories']} comment={preview['comment'][:120]}...")
        return

    print(f"[6/6] Filing reports, banning, and updating blocklists ({len(ban_report)} IP(s))...")
    for r in ban_report:
        ip = r["ip"]
        evidence_json = json.dumps({
            "scanner_hits": r["evidence"]["scanner_hits"],
            "sensitive_hits": r["evidence"]["sensitive_hits"],
        })
        result = json.loads(docker_exec_manage(
            ["security_report_auto", "--ip", ip, "--evidence-json", evidence_json, "--confirm"]
        ))
        ban_ip(ip)
        reported_log[ip] = {
            # AbuseIPDB's /report response has no reportedAt field of its own
            # (unlike /check and /reports) - this is our own submission time.
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "categories": result["categories"],
            "comment": result["comment"],
            "abuse_score": r["score"],
        }
        print(f"      {ip}: reported + permabanned (categories={result['categories']})")

    save_reported_log(reported_log)

    updated_permaban_ips = get_permanent_ban_ips()
    regenerate_block_permanent_sh(updated_permaban_ips)
    print(f"      block_permanent.sh regenerated from current permanent-ban jail "
          f"({len(updated_permaban_ips)} IPs)")

    print("      restarting app container so HardenedBlocklistMiddleware reloads nginx_blocklist.conf...")
    run(["docker", "restart", WEB_CONTAINER])

    print(f"\nDone. {len(ban_report)} IP(s) reported and permabanned.")


if __name__ == "__main__":
    main()
