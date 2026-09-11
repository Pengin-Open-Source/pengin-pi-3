from email.utils import formataddr
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
from dotenv import load_dotenv
from util.mail.ses import SES as Mailer

load_dotenv()


class Message(Mailer):

    def __init__(
        self,
        RECIPIENT,
        TOKEN=None,
        TYPE=None,
        URL=os.getenv("URL"),
        OTP=None,
    ):
        Mailer.__init__(self)
        self.RECIPIENT = RECIPIENT
        self.TOKEN = TOKEN or ""
        self.URL = URL or ""
        self.OTP = OTP or ""

        if TYPE == "staff_account_otp":
            self.SUBJECT = "Activate Your Account"
            BODY_TEXT = (
                f"Activate Your Account\r\nAn administrator created an account for you. "
                f"Your one-time password is: {self.OTP}\r\n"
                f"Use it to set your own password and activate your account at "
                f"https://{self.URL}/activate/{self.TOKEN}"
            )
            BODY_HTML = f"""<html><body><h1>Activate Your Account</h1><p>An administrator created an account for you. Your one-time password is:</p><p style="font-size:20px;font-weight:bold;letter-spacing:2px;">{self.OTP}</p><p>Use it to set your own password and activate your account: <a href='https://{self.URL}/activate/{self.TOKEN}'>Activate Account</a></p></body></html>"""

        elif TYPE == "user_validation":
            self.SUBJECT = "Validation Email"
            BODY_TEXT = (
                f"Validation Email\r\nThis email is an automated message. Verify your"
                f" account at https://{self.URL}/profile/validate/{self.TOKEN}"
            )
            BODY_HTML = f"""<html><body><h1>Validation Email</h1><p>Please validate your email: <a href='https://{self.URL}/profile/validate/{self.TOKEN}'>Account Validation</a></p></body></html>"""

        elif TYPE == "password_reset":
            self.SUBJECT = "Password Reset Email"
            BODY_TEXT = (
                f"Password Reset Email\r\nReset your password at"
                f" https://{self.URL}/reset-password/{self.TOKEN}"
            )
            BODY_HTML = f"""<html><body><h1>Password Reset</h1><p><a href='https://{self.URL}/reset-password/{self.TOKEN}'>Reset password</a></p></body></html>"""

        else:
            self.SUBJECT = "Notification"
            BODY_TEXT = "Notification"
            BODY_HTML = "<html><body><p>Notification</p></body></html>"

        # MIMEMultipart construction
        self.msg = MIMEMultipart("alternative")
        self.msg["Subject"] = self.SUBJECT
        self.msg["From"] = formataddr((self.SENDER_NAME, self.SENDER))
        self.msg["To"] = RECIPIENT
        self.part1 = MIMEText(BODY_TEXT, "plain")
        self.part2 = MIMEText(BODY_HTML, "html")
        self.msg.attach(self.part1)
        self.msg.attach(self.part2)
