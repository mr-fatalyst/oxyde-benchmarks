from __future__ import annotations
from datetime import datetime
from typing import Optional
from oxyde import OxydeModel, Field


class Tag(OxydeModel):
    """Tag model for many-to-many relation."""

    class Meta:
        is_table = True
        table_name = "tags"

    id: int | None = Field(default=None, db_pk=True)
    name: str = Field(max_length=50, db_unique=True)


class PostTag(OxydeModel):
    """Junction table for Post-Tag many-to-many."""

    class Meta:
        is_table = True
        table_name = "post_tags"

    id: int | None = Field(default=None, db_pk=True)
    post: Optional["Post"] = Field(default=None, db_on_delete="CASCADE")
    tag: Optional[Tag] = Field(default=None, db_on_delete="CASCADE")


class User(OxydeModel):
    """User model matching benchmark schema."""

    class Meta:
        is_table = True
        table_name = "users"

    id: int | None = Field(default=None, db_pk=True)
    name: str = Field(max_length=100)
    email: str = Field(max_length=255, db_unique=True)
    age: int
    is_active: bool = True
    created_at: datetime | None = Field(default=None, db_default="NOW()")
    posts: list["Post"] = Field(db_reverse_fk="user")


class Post(OxydeModel):
    """Post model with foreign key to User."""

    class Meta:
        is_table = True
        table_name = "posts"

    id: int | None = Field(default=None, db_pk=True)
    title: str = Field(max_length=200)
    content: str = ""
    views: int = 0
    created_at: datetime | None = Field(default=None, db_default="NOW()")
    user: Optional[User] = Field(default=None, db_on_delete="CASCADE")
    post_tags: list[PostTag] = Field(db_reverse_fk="post")
