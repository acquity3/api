import socketio

from src.services import (
    ChatRoomService,
    ChatService,
    LinkedInLogin,
    OfferService,
    UserService,
)
from src.utils import handle_acquity_exceptions


class ChatSocketService(socketio.AsyncNamespace):
    def __init__(self, namespace, config):
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

    async def on_connect(self, sid, environ):
        return {"data": "success"}

    async def on_disconnect(self, sid):
        return {"data": "success"}

    @handle_acquity_exceptions
    async def on_req_subscribe(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        for chat_room in self.chat_room_service.get_chat_rooms_by_user_id(
            user_id=user_id
        ):
            self.enter_room(sid, chat_room["id"])

    @handle_acquity_exceptions
    async def on_req_new_message(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        room_id = data.get("chat_room_id")
        chat = self.chat_service.create_new_message(
            chat_room_id=data.get("chat_room_id"),
            message=data.get("message"),
            author_id=user_id,
            user_type=data.get("user_type"),
        )

        await self.emit("res_new_event", chat, room=room_id)

    @handle_acquity_exceptions
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
        await self.emit("res_new_event", offer, room=room_id)

    @handle_acquity_exceptions
    async def on_req_accept_offer(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        room_id = data.get("chat_room_id")
        offer = self.offer_service.update_offer(
            chat_room_id=room_id,
            offer_id=data.get("offer_id"),
            user_id=user_id,
            user_type=data.get("user_type"),
            is_accept=True,
        )
        await self.emit("res_new_event", offer, room=room_id)

    @handle_acquity_exceptions
    async def on_req_decline_offer(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        room_id = data.get("chat_room_id")
        offer = self.offer_service.update_offer(
            chat_room_id=room_id,
            offer_id=data.get("offer_id"),
            user_id=user_id,
            user_type=data.get("user_type"),
            is_accept=False,
        )
        await self.emit("res_new_event", offer, room=room_id)

    @handle_acquity_exceptions
    async def on_req_archive_chatroom(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        self.chat_room_service.archive_room(
            user_id=user_id, chat_room_id=data.get("chat_room_id")
        )

    @handle_acquity_exceptions
    async def on_req_disband_chatroom(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        room_id = data.get("chat_room_id")

        rsp = self.chat_room_service.disband_chatroom(
            user_id=user_id, chat_room_id=room_id
        )
        await self.emit("res_disband_chatroom", rsp, room=room_id)

    @handle_acquity_exceptions
    async def on_req_reveal_identity(self, sid, data):
        user_id = await self._authenticate(token=data.get("token"))
        room_id = data.get("chat_room_id")

        rsp = self.chat_room_service.reveal_identity(
            chat_room_id=room_id, user_id=user_id
        )

        if rsp is not None:
            await self.emit("res_reveal_identity", rsp, room=room_id)
