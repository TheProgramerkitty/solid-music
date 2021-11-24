from typing import List, Dict, Tuple
from .scaffold import Scaffold
from configs import config


class ChatDB(Scaffold):
    @staticmethod
    def _get(chats: Tuple) -> List[Dict[str, str]]:
        final = []
        for chat in chats:
            owner_id, chat_id, lang, quality, only_admin = chat
            admin = bool(only_admin)
            x = {
                "owner_id": owner_id,
                "chat_id": chat_id,
                "lang": lang,
                "quality": quality,
                "only_admin": admin
            }
            final.append(x.copy())
        return final

    def get_chat(self, chat_id: int) -> List[Dict[str, str]]:
        results = self.cur.execute("SELECT * FROM chat_db WHERE chat_id = ?", (chat_id,))
        final = self._get(results)
        return final

    def add_chat(
        self,
        chat_id: int,
        lang: str = "en",
        owner_id: int = config.OWNER_ID,
        quality: str = "medium",
        only_admin: bool = False,
    ):
        chats = self.get_chat(chat_id)
        for chat in chats:
            if chat_id == chat["chat_id"]:
                return "already_added_chat"
            return
        self.cur.execute(
            "INSERT INTO chat_db VALUES (?, ?, ?, ?, ?)",
            (owner_id, chat_id, f"{lang}", f"{quality.lower()}", only_admin)
        )
        self.conn.commit()
        return "chat_added"

    def del_chat(self, chat_id: int):
        self.cur.execute("DELETE FROM chat_db WHERE chat_id = ? ", (chat_id,))
        self.conn.commit()
        return "chat_deleted"

    def set_lang(self, chat_id: int, lang: str):
        chats = self.get_chat(chat_id)
        for chat in chats:
            if lang == chat["lang"]:
                return "lang_already_used"
        self.cur.execute(
            """
            UPDATE chat_db
            SET lang = ?
            WHERE chat_id = ?
            """,
            (f"{lang}", chat_id,)
        )
        self.conn.commit()
        return "lang_changed"

    def set_quality(self, chat_id: int, quality: str):
        chats = self.get_chat(chat_id)
        for chat in chats:
            if quality == chat["quality"]:
                return "quality_already_used"
        self.cur.execute(
            """
            UPDATE chat_db
            SET quality = ?
            WHERE chat_id = ?
            """,
            (f"{quality}", chat_id,)
        )
        self.conn.commit()
        return "quality_changed"

    def set_admin(self, chat_id: int, only_admin: bool):
        chats = self.get_chat(chat_id)
        for chat in chats:
            if int(only_admin) == chat["only_admin"]:
                return "only_admin_already_set"
            return
        self.cur.execute(
            """
            UPDATE chat_db
            SET admin_only = ?
            WHERE chat_id = ?
            """,
            (only_admin, chat_id,)
        )
        self.conn.commit()
        return "only_admin_changed"

    def get_stats(self):
        chats = self.cur.execute("SELECT * FROM chat_db")
        group = pm = 0
        results = self._get(chats)
        for result in results:
            chat_id = str(result["chat_id"])
            if chat_id.startswith("-"):
                group += 1
            else:
                pm += 1
        return {"groups": group, "pm": pm}
