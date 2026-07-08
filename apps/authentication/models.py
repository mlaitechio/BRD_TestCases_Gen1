"""
User Profile Models for Role-Based Access Control
"""

from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """
    Extended user profile with role-based access control.
    Roles: Admin (full access) or User (limited access)
    """

    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('user', 'User'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='user',
        help_text='User role: Admin has full access, User has limited access'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this user account is active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'

    @property
    def is_admin(self):
        """Check if user is admin"""
        return self.role == 'admin' and self.is_active

    @property
    def is_user(self):
        """Check if user is regular user"""
        return self.role == 'user' and self.is_active
