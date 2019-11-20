from functools import wraps

import socketio

from src.exceptions import AcquityException
from src.services import (
    ChatRoomService,
    ChatService,
    LinkedInLogin,
    OfferService,
    UserService,
)


def handle_acquity_exceptions(f):
    @wraps(f)
    async def decorated(self, sid, *args, **kwargs):
        try:
            return await f(self, sid, *args, **kwargs)
        except AcquityException as e:
            # on_req_* => req_*
            channel_name = f.__name__[3:]
            await self.emit(
                "error", {"name": channel_name, "message": e.message}, room=sid
            )

    return decorated


def auth_required(f):
    @wraps(f)
    async def decorated(self, sid, data):
        token = data.get("token")
        if token is None:
            pass

        linkedin_user = self.linkedin_login.get_linkedin_user(token=token)
        user = self.user_service.get_user_by_linkedin_id(
            provider_user_id=linkedin_user["provider_user_id"]
        )

        data.pop("token")
        return await f(self, sid, data, user)

    return decorated


class ChatSocketService(socketio.AsyncNamespace):
    def __init__(self, namespace, config):
        super().__init__(namespace)
        self.chat_service = ChatService(config)
        self.chat_room_service = ChatRoomService(config)
        self.linkedin_login = LinkedInLogin(config)
        self.user_service = UserService(config)
        self.offer_service = OfferService(config)
        self.config = config

    async def on_connect(self, sid, environ):
        return {"data": "success"}

    async def on_disconnect(self, sid):
        return {"data": "success"}

    @handle_acquity_exceptions
    @auth_required
    async def on_req_subscribe(self, sid, data, user):
        chat_rooms = self.chat_room_service.get_chat_rooms_by_user_id(
            user_id=user["id"]
        )
        for chat_room in chat_rooms:
            self.enter_room(sid, chat_room["id"])

    @handle_acquity_exceptions
    @auth_required
    async def on_req_new_message(self, sid, data, user):
        chat = self.chat_service.create_new_message(**data, author_id=user["id"])
        await self.emit("res_new_event", chat, room=data["chat_room_id"])

    @handle_acquity_exceptions
    @auth_required
    async def on_req_new_offer(self, sid, data, user):
        offer = self.offer_service.create_new_offer(**data, author_id=user["id"])
        await self.emit("res_new_event", offer, room=data["chat_room_id"])

    @handle_acquity_exceptions
    @auth_required
    async def on_req_edit_offer_status(self, sid, data, user):
        resp = self.offer_service.edit_offer_status(**data, user_id=user["id"])
        await self.emit("res_new_event", resp, room=data["chat_room_id"])

    @handle_acquity_exceptions
    @auth_required
    async def on_req_archive_chatroom(self, sid, data, user):
        self.chat_room_service.archive_room(**data, user_id=user["id"])

    @handle_acquity_exceptions
    @auth_required
    async def on_req_disband_chatroom(self, sid, data, user):
        rsp = self.chat_room_service.disband_chatroom(**data, user_id=user["id"])
        await self.emit("res_disband_chatroom", rsp, room=data["chat_room_id"])

    @handle_acquity_exceptions
    @auth_required
    async def on_req_update_last_read_id(self, sid, data, user):
        self.chat_room_service.update_last_read_id(**data, user_id=user["id"])

    @handle_acquity_exceptions
    @auth_required
    async def on_req_reveal_identity(self, sid, data, user):
        rsp = self.chat_room_service.reveal_identity(**data, user_id=user["id"])

        if rsp is not None:
            await self.emit("res_reveal_identity", rsp, room=data["chat_room_id"])
