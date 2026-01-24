from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, Relationship


class User(SQLModel, table=True):
    """User model matching benchmark schema."""

    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100)
    email: str = Field(max_length=255, unique=True)
    age: int
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    posts: list["Post"] = Relationship(back_populates="user")


class Post(SQLModel, table=True):
    """Post model with foreign key to User."""

    __tablename__ = "posts"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    title: str = Field(max_length=200)
    content: str = Field(default="")
    views: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    user: Optional[User] = Relationship(back_populates="posts")
    post_tags: list["PostTag"] = Relationship(back_populates="post")


class Tag(SQLModel, table=True):
    """Tag model for many-to-many relation."""

    __tablename__ = "tags"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True)

    post_tags: list["PostTag"] = Relationship(back_populates="tag")


class PostTag(SQLModel, table=True):
    """Junction table for Post-Tag many-to-many."""

    __tablename__ = "post_tags"

    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="posts.id")
    tag_id: int = Field(foreign_key="tags.id")

    post: Optional[Post] = Relationship(back_populates="post_tags")
    tag: Optional[Tag] = Relationship(back_populates="post_tags")
