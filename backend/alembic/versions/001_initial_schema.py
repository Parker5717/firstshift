"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('slug', sa.String(64), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_tenants_slug', 'tenants', ['slug'], unique=True)

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('display_name', sa.String(128), nullable=False, server_default=''),
        sa.Column('password_hash', sa.String(128), nullable=True),
        sa.Column('role', sa.String(16), nullable=False, server_default='employee'),
        sa.Column('mentor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('total_xp', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_active_at', sa.DateTime(), nullable=False),
        sa.Column('privacy_accepted_at', sa.DateTime(), nullable=True),
        sa.Column('birth_year', sa.Integer(), nullable=True),
        sa.Column('ui_mode', sa.String(16), nullable=False, server_default='gamified'),
        sa.UniqueConstraint('tenant_id', 'username', name='uq_tenant_username'),
    )
    op.create_index('ix_users_tenant_id', 'users', ['tenant_id'])
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_mentor_id', 'users', ['mentor_id'])

    op.create_table(
        'quests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True),
        sa.Column('slug', sa.String(64), nullable=False, unique=True),
        sa.Column('title', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('type', sa.String(32), nullable=False),
        sa.Column('target_class', sa.String(64), nullable=True),
        sa.Column('target_marker_id', sa.Integer(), nullable=True),
        sa.Column('xp_reward', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('prerequisite_slug', sa.String(64), nullable=True),
        sa.Column('story_chapter', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('difficulty', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('params_json', sa.Text(), nullable=False, server_default='{}'),
    )
    op.create_index('ix_quests_slug', 'quests', ['slug'], unique=True)
    op.create_index('ix_quests_tenant_id', 'quests', ['tenant_id'])

    op.create_table(
        'achievements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True),
        sa.Column('slug', sa.String(64), nullable=False, unique=True),
        sa.Column('title', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('icon', sa.String(64), nullable=False, server_default='trophy'),
        sa.Column('condition_json', sa.Text(), nullable=False),
        sa.Column('xp_bonus', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('ix_achievements_slug', 'achievements', ['slug'], unique=True)
    op.create_index('ix_achievements_tenant_id', 'achievements', ['tenant_id'])

    op.create_table(
        'user_quest_progress',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('quest_id', sa.Integer(), sa.ForeignKey('quests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='locked'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'quest_id', name='uq_user_quest'),
    )
    op.create_index('ix_user_quest_progress_user_id', 'user_quest_progress', ['user_id'])
    op.create_index('ix_user_quest_progress_quest_id', 'user_quest_progress', ['quest_id'])

    op.create_table(
        'user_achievements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('achievement_id', sa.Integer(), sa.ForeignKey('achievements.id', ondelete='CASCADE'), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('user_id', 'achievement_id', name='uq_user_achievement'),
    )
    op.create_index('ix_user_achievements_user_id', 'user_achievements', ['user_id'])
    op.create_index('ix_user_achievements_achievement_id', 'user_achievements', ['achievement_id'])

    op.create_table(
        'scan_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('detected_class', sa.String(64), nullable=True),
        sa.Column('marker_id', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('quest_id', sa.Integer(), sa.ForeignKey('quests.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_scan_events_user_id', 'scan_events', ['user_id'])
    op.create_index('ix_scan_events_timestamp', 'scan_events', ['timestamp'])

    op.create_table(
        'safety_checks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('passed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('helmet', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('vest', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('goggles', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('missing_items', sa.String(256), nullable=False, server_default=''),
        sa.Column('client_id', sa.String(64), nullable=True),
        sa.UniqueConstraint('user_id', 'client_id', name='uq_safety_client'),
    )
    op.create_index('ix_safety_checks_user_id', 'safety_checks', ['user_id'])
    op.create_index('ix_safety_checks_timestamp', 'safety_checks', ['timestamp'])
    op.create_index('ix_safety_checks_client_id', 'safety_checks', ['client_id'])


def downgrade() -> None:
    op.drop_table('safety_checks')
    op.drop_table('scan_events')
    op.drop_table('user_achievements')
    op.drop_table('user_quest_progress')
    op.drop_table('achievements')
    op.drop_table('quests')
    op.drop_table('users')
    op.drop_table('tenants')
