from django.db import models


class User(models.Model):
    """User model matching benchmark schema."""

    name = models.CharField(max_length=100)
    email = models.CharField(max_length=255, unique=True)
    age = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"
        app_label = "django_bench"


class Post(models.Model):
    """Post model with foreign key to User."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        db_column="user_id",
    )
    title = models.CharField(max_length=200)
    content = models.TextField(default="")
    views = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "posts"
        app_label = "django_bench"


class Tag(models.Model):
    """Tag model for many-to-many relation."""

    name = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = "tags"
        app_label = "django_bench"


class PostTag(models.Model):
    """Junction table for Post-Tag many-to-many."""

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        db_column="post_id",
    )
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        db_column="tag_id",
    )

    class Meta:
        db_table = "post_tags"
        app_label = "django_bench"
