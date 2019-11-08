import socketio

from src.exceptions import AcquityException
from src.services import (
    ChatRoomService,
    ChatService,
    LinkedInLogin,
    OfferService,
    UserService,
)


def handle_acquity_exceptions(emit_message):
    def decorator(f):
        async def decorated(self, sid, *args, **kwargs):
            try:
                return await f(self, sid, *args, **kwargs)
            except AcquityException as e:
                await self.emit(
                    emit_message,
                    {"status_code": e.status_code, "message": e.message},
                    room=sid,
                )

        return decorated

    return decorator


class ChatSocketService(socketio.AsyncNamespace):
    def __init__(self, namespace, config, sio):
        super().__init__(namespace)
        self.chat_service = ChatService(config)
        self.chat_room_service = ChatRoomService(config)
        self.linkedin_login = LinkedInLogin(config)
        self.user_service = UserService(config)
        self.offer_service = OfferService(config)
        self.config = config

    async def _authenticate(self, token):
        linkedin_user = self.linkedin_login.get_user_profile(token=token)
        user = self.user_service.get_user_by_linkedin_id(
            provider_user_id=linkedin_user.get("provider_user_id")
        )
        return user.get("id")

    async def _get_chat_rooms(self, sid, user_id, user_type, is_archived):
        rooms = self.chat_room_service.get_chat_rooms(
            user_id=user_id, user_type=user_type, is_archived=is_archived
        )
        for room in rooms:
            self.enter_room(sid, room.get("chat_room_id"))
        self.enter_room(sid, user_id)
        return rooms

    async def on_connect(self, sid, environ):
        return {"data": "success"}

    async def on_disconnect(self, sid):
        return {"data": "success"}

    @handle_acquity_exceptions("err_chat_rooms")
    async def on_req_chat_rooms(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        rooms = await self._get_chat_rooms(
            sid=sid,
            user_id=user_id,
            user_type=data.get("user_type"),
            is_archived=data.get("is_archived"),
        )
        await self.emit("res_chat_rooms", rooms, room=user_id)

    @handle_acquity_exceptions("err_conversation")
    async def on_req_conversation(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        conversation = self.chat_service.get_conversation(
            user_id=user_id,
            chat_room_id=data.get("chat_room_id"),
            user_type=data.get("user_type"),
        )
        await self.emit("res_conversation", conversation, room=user_id)

    @handle_acquity_exceptions("err_new_message")
    async def on_req_new_message(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        room_id = data.get("chat_room_id")
        chat = self.chat_service.create_new_message(
            chat_room_id=data.get("chat_room_id"),
            message=data.get("message"),
            author_id=user_id,
            user_type=data.get("user_type"),
        )

        await self.emit("res_new_message", chat, room=room_id)

    @handle_acquity_exceptions("err_new_offer")
    async def on_req_new_offer(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        room_id = data.get("chat_room_id")
        offer = self.offer_service.create_new_offer(
            author_id=user_id,
            chat_room_id=data.get("chat_room_id"),
            price=data.get("price"),
            number_of_shares=data.get("number_of_shares"),
            user_type=data.get("user_type"),
        )
        await self.emit("res_new_offer", offer, room=room_id)

    @handle_acquity_exceptions("err_accept_offer")
    async def on_req_accept_offer(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        room_id = data.get("chat_room_id")
        offer = self.offer_service.accept_offer(
            chat_room_id=room_id,
            offer_id=data.get("offer_id"),
            user_id=user_id,
            user_type=data.get("user_type"),
        )
        await self.emit("res_accept_offer", offer, room=room_id)

    @handle_acquity_exceptions("err_decline_offer")
    async def on_req_decline_offer(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        room_id = data.get("chat_room_id")
        offer = self.offer_service.reject_offer(
            chat_room_id=room_id,
            offer_id=data.get("offer_id"),
            user_id=user_id,
            user_type=data.get("user_type"),
        )
        await self.emit("res_decline_offer", offer, room=room_id)

    @handle_acquity_exceptions("err_reveal_identity")
    async def on_req_reveal_identity(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        room_id = data.get("chat_room_id")

        self.chat_room_service.reveal_identity(chat_room_id=room_id, user_id=user_id)

        await self.emit("res_reveal_identity", {}, room=room_id)

    @handle_acquity_exceptions("err_other_party_details")
    async def on_req_other_party_details(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        room_id = data.get("chat_room_id")

        other_party_details = self.chat_room_service.get_other_party_details(
            chat_room_id=room_id, user_id=user_id
        )

        await self.emit("res_other_party_details", other_party_details, room=room_id)
