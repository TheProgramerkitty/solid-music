import random

from pyrogram.errors import ChatIdInvalid, ChannelInvalid
from pyrogram.raw.base import InputChannel, InputGroupCall
from pyrogram.raw.functions.channels import GetFullChannel
from pyrogram.raw.functions.messages import GetFullChat
from pyrogram.raw.functions.phone import CreateGroupCall, DiscardGroupCall
from pyrogram.raw.types import InputPeerChannel
from pytgcalls.types import Update
from pytgcalls.types.input_stream import AudioPiped, AudioVideoPiped
from pytgcalls.types.input_stream.quality import (
    LowQualityAudio,
    MediumQualityAudio,
    HighQualityAudio,
    LowQualityVideo,
    MediumQualityVideo,
    HighQualityVideo,
)
from pytgcalls.types.stream import StreamAudioEnded

from functions.youtube_utils import get_audio_direct_link, get_video_direct_link
from .clients import user, call_py
from .bot import Bot
from .queue import Queue
from database.chat_database import ChatDB
from database.sudo_database import SudoDB


class Methods(ChatDB, SudoDB):
    def __init__(self):
        super(Methods, self).__init__()


class Call:
    def __init__(self):
        self.call = call_py
        self.user = user
        self.bot = Bot()
        self.playlist = Queue()
        self.db = Methods()

        @self.call.on_stream_end()
        async def _(_, update: Update):
            if isinstance(update, StreamAudioEnded):
                chat_id = update.chat_id
                await self.check_playlist(chat_id)

        @self.call.on_kicked()
        @self.call.on_left()
        @self.call.on_closed_voice_chat()
        async def __(_, chat_id: int):
            return self.playlist.delete_chat(chat_id)

    def get_quality(self, chat_id):
        quality: str = self.db.get_chat(chat_id)[0]["quality"]
        if quality not in ["low", "medium", "high"]:
            raise KeyError("Invalid Quality")
        if quality == "low":
            audio_quality = LowQualityAudio()
            video_quality = LowQualityVideo()
        elif quality == "medium":
            audio_quality = MediumQualityAudio()
            video_quality = MediumQualityVideo()
        else:
            audio_quality = HighQualityAudio()
            video_quality = HighQualityVideo()
        return audio_quality, video_quality

    def init_youtube_player(
        self,
        chat_id: int,
        user_id: int,
        title: str,
        duration: str,
        yt_url: str,
        yt_id: str,
        stream_type: str,
    ):
        objects = {
            "user_id": user_id,
            "title": title,
            "duration": duration,
            "yt_url": yt_url,
            "yt_id": yt_id,
            "stream_type": stream_type,
        }
        return self.playlist.insert_one(chat_id, objects)

    def init_telegram_player(
        self,
        chat_id: int,
        user_id: int,
        title: str,
        duration: str,
        source_file: str,
        stream_type: str,
    ):
        objects = {
            "user_id": user_id,
            "title": title,
            "duration": duration,
            "source_file": source_file,
            "stream_type": stream_type,
        }
        return self.playlist.insert_one(chat_id, objects)

    def is_call_active(self, chat_id: int):
        call = self.call
        for active_call in call.active_calls:
            return bool(chat_id == getattr(active_call, "chat_id"))
        return False

    async def _get_group_call(self, chat_id: int) -> InputGroupCall:
        # Credit Userge
        chat_peer = await self.user.resolve_peer(chat_id)
        if isinstance(chat_peer, (InputPeerChannel, InputChannel)):
            full_chat = (
                await self.user.send(GetFullChannel(channel=chat_peer))
            ).full_chat
        else:
            full_chat = (
                await self.user.send(GetFullChat(chat_id=chat_peer.chat_id))
            ).full_chat
        if full_chat:
            return full_chat.call

    async def start_call(self, chat_id: int):
        users = self.user
        try:
            await users.send(
                CreateGroupCall(
                    peer=await users.resolve_peer(chat_id),
                    random_id=random.randint(10000, 999999999),
                )
            )
            await self.bot.send_message(chat_id, "call_started")
        except (ChatIdInvalid, ChannelInvalid):
            link = await self.bot.export_chat_invite_link(chat_id)
            await users.join_chat(link)
            user_id = (await users.get_me()).id
            await self.bot.promote_member(chat_id, user_id)
            await self.start_call(chat_id)

    async def end_call(self, chat_id: int):
        # Credit Userge
        call = await self._get_group_call(chat_id)
        await self.user.send(DiscardGroupCall(call=call))
        await self.bot.send_message(chat_id, "call_ended")

    async def change_vol(self, chat_id: int, volume: int):
        call = self.call
        is_active = self.is_call_active(chat_id)
        if is_active:
            await call.change_volume_call(chat_id, volume)
            return await self.bot.send_message(chat_id, "volume_changed", str(volume))
        return await self.bot.send_message(chat_id, "not_in_call")

    async def change_streaming_status(self, status: str, chat_id: int):
        call = self.call
        is_active = self.is_call_active(chat_id)
        if is_active:
            if status == "pause":
                await call.pause_stream(chat_id)
                return "track_paused"
            if status == "resume":
                await call.resume_stream(chat_id)
                return "track_resumed"
        else:
            return "not_in_call"

    async def end_stream(self, chat_id: int):
        call = self.call
        is_active = self.is_call_active(chat_id)
        if is_active:
            await call.leave_group_call(chat_id)
            self.playlist.delete_chat(chat_id)
            return "stream_ended"
        return "not_in_call"

    async def _change_stream(self, chat_id: int):
        playlist = self.playlist
        playlist.delete_one(chat_id)
        yt_url = playlist.get(chat_id)["yt_url"]
        title = playlist.get(chat_id)["title"]
        stream_type = playlist.get(chat_id)["stream_type"]
        await self._stream_change(chat_id, yt_url, stream_type)
        return title

    async def _stream_change(self, chat_id: int, yt_url: str, stream_type: str):
        call = self.call
        if stream_type == "music":
            audio_quality = self.db.get_chat(chat_id)[0]["quality"]
            url = get_audio_direct_link(yt_url)
            if audio_quality == "low":
                quality = LowQualityAudio()
            elif audio_quality == "medium":
                quality = MediumQualityAudio()
            else:
                quality = HighQualityAudio()
            await call.change_stream(chat_id, AudioPiped(url, quality))
        elif stream_type == "video":
            quality = self.db.get_chat(chat_id)[0]["quality"]
            url = get_video_direct_link(yt_url)
            if quality == "low":
                video_quality = LowQualityVideo()
                audio_quality = LowQualityAudio()
            elif quality == "medium":
                video_quality = MediumQualityVideo()
                audio_quality = MediumQualityAudio()
            else:
                video_quality = HighQualityVideo()
                audio_quality = HighQualityAudio()
            await call.change_stream(
                chat_id, AudioVideoPiped(url, audio_quality, video_quality)
            )

    async def check_playlist(self, chat_id: int):
        playlist = self.playlist.playlist
        call = self.call
        if playlist and chat_id in playlist:
            if len(playlist[chat_id]) > 1:
                title = await self._change_stream(chat_id)
                await self.bot.send_message(chat_id, "track_changed", title)
            elif len(playlist[chat_id]) == 1:
                await call.leave_group_call(chat_id)
                self.playlist.delete_chat(chat_id)
        else:
            await call.leave_group_call(chat_id)

    async def change_stream(self, chat_id: int):
        playlist = self.playlist.playlist
        if chat_id in playlist and len(playlist[chat_id]) > 1:
            title = await self._change_stream(chat_id)
            return await self.bot.send_message(chat_id, "track_skipped", title)
        return await self.bot.send_message(chat_id, "no_playlists")

    def send_playlist(self, chat_id: int):
        playlist = self.playlist.playlist
        if chat_id in playlist:
            current = playlist[chat_id][0]
            queued = playlist[chat_id][1:]
            return current, queued
        return None, None
