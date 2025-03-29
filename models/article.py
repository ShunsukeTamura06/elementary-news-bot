# models/article.py
from datetime import datetime
from typing import Optional


class Article:
    """記事モデル"""

    def __init__(
        self,
        title: str,
        content: str,
        status: str = "draft",
        created_at: datetime = None,
        published_at: Optional[datetime] = None,
        improved_content: Optional[str] = None,
    ):
        """
        記事モデルの初期化

        Args:
            title: 記事のタイトル
            content: 記事の内容
            status: 記事の状態 ("draft" または "published")
            created_at: 記事の作成日時
            published_at: 記事の公開日時（公開前はNone）
            improved_content: 改善された記事の内容（改善前はNone）
        """
        self.title = title
        self.content = content
        self.status = status
        self.created_at = created_at or datetime.now()
        self.published_at = published_at
        self.improved_content = improved_content

    def __str__(self) -> str:
        """記事の文字列表現"""
        return f"Article(title='{self.title}', status='{self.status}')"

    def to_dict(self) -> dict:
        """記事を辞書形式に変換"""
        return {
            "title": self.title,
            "content": self.content,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "improved_content": self.improved_content,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        """辞書から記事オブジェクトを作成"""
        created_at = (
            datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None
        )
        published_at = (
            datetime.fromisoformat(data["published_at"]) if data.get("published_at") else None
        )
        
        return cls(
            title=data["title"],
            content=data["content"],
            status=data.get("status", "draft"),
            created_at=created_at,
            published_at=published_at,
            improved_content=data.get("improved_content"),
        )