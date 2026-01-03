from typing import Optional, Dict, Any
import boto3


class SesMailer:
    def __init__(
        self,
        region: str,
        access_key_id: Optional[str],
        secret_access_key: Optional[str],
        from_email: Optional[str],
        to_email: Optional[str],
        configuration_set: Optional[str] = None,
    ):
        self.from_email = from_email
        self.to_email = to_email
        self.configuration_set = configuration_set

        self.client = boto3.client(
            "ses",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def send_inquiry(self, name: str, email: str, message: str) -> Dict[str, Any]:
        if not self.from_email or not self.to_email:
            raise RuntimeError("SES_FROM_EMAIL / SES_TO_EMAIL not configured")

        subject = f"New Inquiry from {name}"
        body_text = (
            "New message from website chatbot:\n\n"
            f"Name: {name}\n"
            f"Email: {email}\n\n"
            "Message:\n"
            f"{message}\n"
        )

        req = {
            "Source": self.from_email,
            "Destination": {"ToAddresses": [self.to_email]},
            "Message": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
            },
        }
        if self.configuration_set:
            req["ConfigurationSetName"] = self.configuration_set

        resp = self.client.send_email(**req)
        return {"messageId": resp.get("MessageId")}