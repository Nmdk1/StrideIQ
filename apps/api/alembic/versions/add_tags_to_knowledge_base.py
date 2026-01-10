"""Add JSONB tags column to coaching_knowledge_entry

Revision ID: add_tags_kb
Revises: 28b8df012709
Create Date: 2026-01-04 16:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_tags_kb'
down_revision = '28b8df012709'  # Knowledge base tables migration
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add JSONB tags column
    op.add_column(
        'coaching_knowledge_entry',
        sa.Column('tags', postgresql.JSONB, nullable=True)
    )
    
    # Create GIN index for efficient JSONB queries
    op.create_index(
        'ix_knowledge_tags_gin',
        'coaching_knowledge_entry',
        ['tags'],
        postgresql_using='gin',
        unique=False
    )
    
    # Create index for tag existence queries (? operator)
    # Note: GIN index already supports ?, @>, and other JSONB operators
    # But we can add a functional index for specific queries if needed


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_knowledge_tags_gin', table_name='coaching_knowledge_entry')
    
    # Drop column
    op.drop_column('coaching_knowledge_entry', 'tags')

