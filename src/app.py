import traceback

import sentry_sdk
import socketio
from sanic import Sanic
from sanic.exceptions import SanicException
from sanic.response import json
from sanic_cors.extension import CORS as initialize_cors
from sentry_sdk.integrations.sanic import SanicIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from src.api import blueprint
from src.chat_service import ChatSocketService
from src.config import APP_CONFIG
from src.exceptions import AcquityException
from src.scheduler import scheduler
from src.services import (
    BannedPairService,
    BuyOrderService,
    ChatRoomService,
    ChatService,
    LinkedInLogin,
    MatchService,
    RoundService,
    SecurityService,
    SellOrderService,
    UserRequestService,
    UserService,
)
from src.utils import JsonStrDefault

if APP_CONFIG["SENTRY_ENABLE"]:

    def sentry_before_send(event, hint):
        if "exc_info" in hint:
            _exc_type, exc_value, _tb = hint["exc_info"]
            if isinstance(exc_value, AcquityException):
                return None
        return event

    sentry_sdk.init(
        dsn="https://1d45f7681dca45e8b8a83842dd6303b8@sentry.io/1800796",
        integrations=[SanicIntegration(), SqlalchemyIntegration()],
        before_send=sentry_before_send,
    )

app = Sanic(load_env=False)
app.config.update(APP_CONFIG)

sio = socketio.AsyncServer(
    async_mode="sanic", cors_allowed_origins=[], json=JsonStrDefault
)
sio.attach(app)
sio.register_namespace(ChatSocketService("/v1/chat", app.config))

app.user_service = UserService(app.config)
app.sell_order_service = SellOrderService(app.config)
app.buy_order_service = BuyOrderService(app.config)
app.security_service = SecurityService(app.config)
app.round_service = RoundService(app.config)
app.match_service = MatchService(app.config)
app.banned_pair_service = BannedPairService(app.config)
app.chat_room_service = ChatRoomService(app.config)
app.chat_service = ChatService(app.config)
app.linkedin_login = LinkedInLogin(app.config)
app.user_request_service = UserRequestService(app.config)

initialize_cors(app)


app.blueprint(blueprint)


async def error_handler(request, exception):
    if isinstance(exception, AcquityException):
        if exception.status_code == 404:
            message = f"Requested URL {request.path} not found"
        else:
            message = exception.message

        return json({"error": message}, status=exception.status_code)
    elif isinstance(exception, SanicException):
        return json({"error": exception.args}, status=exception.status_code)
    traceback.print_exc()
    return json({"error": "An internal error occured."}, status=500)


app.error_handler.add(Exception, error_handler)


@app.listener("after_server_start")
async def start_scheduler(app, loop):
    scheduler.configure(event_loop=loop)
    app.scheduler = scheduler
    scheduler.start()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=app.config["PORT"])
