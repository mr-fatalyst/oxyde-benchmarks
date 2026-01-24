from piccolo.table import Table
from piccolo.columns import (
    Serial,
    Varchar,
    Integer,
    Boolean,
    Timestamp,
    Text,
    ForeignKey,
)


class User(Table, tablename="users"):
    """User model matching benchmark schema."""

    id = Serial(primary_key=True)
    name = Varchar(length=100, required=True)
    email = Varchar(length=255, required=True, unique=True)
    age = Integer(required=True)
    is_active = Boolean(default=True, required=True)
    created_at = Timestamp()


class Post(Table, tablename="posts"):
    """Post model with foreign key to User."""

    id = Serial(primary_key=True)
    user_id = ForeignKey(references=User)
    title = Varchar(length=200, required=True)
    content = Text(default="", required=True)
    views = Integer(default=0, required=True)
    created_at = Timestamp()


class Tag(Table, tablename="tags"):
    """Tag model for many-to-many relation."""

    id = Serial(primary_key=True)
    name = Varchar(length=50, required=True, unique=True)


class PostTag(Table, tablename="post_tags"):
    """Junction table for Post-Tag many-to-many."""

    id = Serial(primary_key=True)
    post_id = ForeignKey(references=Post)
    tag_id = ForeignKey(references=Tag)
