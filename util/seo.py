# util/seo.py
def build_organization_schema(site, description="", url=""):
    """
    Builds a schema.org ProfessionalService dict from a Site (or
    util.defaults.default.Site stub) instance, for a page to pass into
    templates/js/json-ld.html as `jsonld`:

        {% include "js/json-ld.html" with jsonld=organization_schema %}

    Opt-in per page (not a context processor) since JSON-LD only belongs
    on pages that actually declare a {% block jsonld %}, not every page.
    """
    schema = {
        "@context": "https://schema.org",
        "@type": "ProfessionalService",
        "name": site.company_name,
    }
    if description:
        schema["description"] = description
    if url:
        schema["url"] = url
    if site.phone:
        schema["telephone"] = site.phone
    if site.address1 or site.city:
        schema["address"] = {
            "@type": "PostalAddress",
            "streetAddress": site.address1,
            "addressLocality": site.city,
            "addressRegion": site.state,
            "postalCode": site.zipcode,
            "addressCountry": site.country,
        }
    return schema
