from tortoise import fields
from tortoise.models import Model


class User(Model):
    """User model matching benchmark schema."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    email = fields.CharField(max_length=255, unique=True)
    age = fields.IntField()
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    posts: fields.ReverseRelation["Post"]

    class Meta:
        table = "users"


class Post(Model):
    """Post model with foreign key to User."""

    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="posts")
    title = fields.CharField(max_length=200)
    content = fields.TextField(default="")
    views = fields.IntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)

    post_tags: fields.ReverseRelation["PostTag"]

    class Meta:
        table = "posts"


class Tag(Model):
    """Tag model for many-to-many relation."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)

    post_tags: fields.ReverseRelation["PostTag"]

    class Meta:
        table = "tags"


class PostTag(Model):
    """Junction table for Post-Tag many-to-many."""

    id = fields.IntField(pk=True)
    post = fields.ForeignKeyField("models.Post", related_name="post_tags")
    tag = fields.ForeignKeyField("models.Tag", related_name="post_tags")

    class Meta:
        table = "post_tags"
