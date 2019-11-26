import json

import requests

EMAIL_TEMPLATE = {
    "register_buyer": {
        "subject": "Welcome to Acquity!",
        "html": "emails/register/buyer.html",
    },
    "register_seller": {
        "subject": "Welcome to Acquity!",
        "html": "emails/register/seller.html",
    },
    "approved_buyer": {
        "subject": "Your account has been approved",
        "html": "emails/approved/buyer.html",
    },
    "approved_seller": {
        "subject": "Your account has been approved",
        "html": "emails/approved/seller.html",
    },
    "rejected_buyer": {
        "subject": "Sorry, your account was not approved",
        "html": "emails/rejected/buyer.html",
    },
    "rejected_seller": {
        "subject": "Sorry, your account was not approved",
        "html": "emails/rejected/seller.html",
    },
    "round_opened_buyer": {
        "subject": "Round Has Opened!",
        "html": "emails/round_opened/buyer.html",
        "templates": {"[START DATE]": "start_date", "[END DATE]": "end_date"},
    },
    "round_opened_seller": {
        "subject": "Round Has Opened!",
        "html": "emails/round_opened/seller.html",
        "templates": {"[START DATE]": "start_date", "[END DATE]": "end_date"},
    },
    "round_closing_soon_buyer": {
        "subject": "Round will be closing in 2 days!",
        "html": "emails/round_closing/buyer.html",
        "templates": {"[END DATE]": "end_date"},
    },
    "round_closing_soon_seller": {
        "subject": "Round will be closing in 2 days!",
        "html": "emails/round_closing/seller.html",
        "templates": {"[END DATE]": "end_date"},
    },
    "create_buy_order": {
        "subject": "Your bid has been created",
        "html": "emails/create_order/buyer.html",
    },
    "create_sell_order": {
        "subject": "Your ask has been created",
        "html": "emails/create_order/seller.html",
    },
    "edit_buy_order": {
        "subject": "Your bid has been edited",
        "html": "emails/edit_order/buyer.html",
    },
    "edit_sell_order": {
        "subject": "Your ask has been edited",
        "html": "emails/edit_order/seller.html",
    },
    "match_done_has_match_buyer": {
        "subject": "You got a match!",
        "html": "emails/match/buyer.html",
    },
    "match_done_has_match_seller": {
        "subject": "You got a match!",
        "html": "emails/match/seller.html",
    },
    "match_done_no_match": {
        "subject": "We could not find you a match",
        "html": "emails/no_match.html",
    },
    "new_chat_message": {
        "subject": "You've got a new message on Acquity",
        "html": "emails/chat_message.html",
    },
    "new_user_review": {
        "subject": "A new user has registered!",
        "html": "emails/admin_new_user.html",
    },
}


class EmailService:
    def __init__(self, config):
        self.config = config

    def send_email(self, emails, template, **kwargs):
        if not self.config["MAILGUN_ENABLE"]:
            return

        data = EMAIL_TEMPLATE[template]
        send_data = {
            "from": "Acquity <noreply@acquity.io>",
            "to": emails,
            "recipient-variables": json.dumps({email: {} for email in emails}),
            "subject": data["subject"],
        }

        if "text" in data:
            send_data["text"] = data["text"]
            if "templates" in data:
                for k, v in data["templates"].items():
                    send_data["text"] = send_data["text"].replace(k, kwargs[v])
        if "html" in data:
            with open(data["html"]) as f:
                send_data["html"] = f.read()
            if "templates" in data:
                for k, v in data["templates"].items():
                    send_data["html"] = send_data["html"].replace(k, kwargs[v])

        return requests.post(
            f"{self.config['MAILGUN_API_BASE_URL']}/messages",
            auth=("api", self.config["MAILGUN_API_KEY"]),
            data=send_data,
        )
