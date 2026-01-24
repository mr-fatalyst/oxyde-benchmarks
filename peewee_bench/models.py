from datetime import datetime

from peewee import (
    Model,
    CharField,
    IntegerField,
    BooleanField,
    DateTimeField,
    ForeignKeyField,
    TextField,
)


# Database proxy - will be set during setup
db_proxy = None


class BaseModel(Model):
    """Base model for all models."""

    class Meta:
        legacy_table_names = False


class User(BaseModel):
    """User model matching benchmark schema."""

    id = IntegerField(primary_key=True)
    name = CharField(max_length=100)
    email = CharField(max_length=255, unique=True)
    age = IntegerField()
    is_active = BooleanField(default=True)
    created_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        table_name = "users"


class Post(BaseModel):
    """Post model with foreign key to User."""

    id = IntegerField(primary_key=True)
    user = ForeignKeyField(User, backref="posts", column_name="user_id")
    title = CharField(max_length=200)
    content = TextField(default="")
    views = IntegerField(default=0)
    created_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        table_name = "posts"


class Tag(BaseModel):
    """Tag model for many-to-many relation."""

    id = IntegerField(primary_key=True)
    name = CharField(max_length=50, unique=True)

    class Meta:
        table_name = "tags"


class PostTag(BaseModel):
    """Junction table for Post-Tag many-to-many."""

    id = IntegerField(primary_key=True)
    post = ForeignKeyField(Post, backref="post_tags", column_name="post_id")
    tag = ForeignKeyField(Tag, backref="post_tags", column_name="tag_id")

    class Meta:
        table_name = "post_tags"
