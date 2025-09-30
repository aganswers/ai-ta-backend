"""
Background sync scheduler for Google Drive integrations.
Runs periodic sync jobs to keep files up-to-date.
"""

import os
from datetime import datetime, timedelta
from typing import List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..database.sql import SQLDatabase
from .google_drive import GoogleDriveService


class DriveSync:
    """Background sync service for drive integrations."""
    
    def __init__(self, sql_db: SQLDatabase, drive_service: GoogleDriveService):
        self.sql_db = sql_db
        self.drive_service = drive_service
        self.scheduler = BackgroundScheduler()
        
    def start_scheduler(self):
        """Start the background scheduler."""
        if not self.scheduler.running:
            # Schedule sync every hour
            self.scheduler.add_job(
                func=self.sync_all_projects,
                trigger=CronTrigger(minute=0),  # Run every hour at minute 0
                id='drive_sync_hourly',
                name='Google Drive Sync (Hourly)',
                replace_existing=True
            )
            
            # Schedule daily cleanup
            self.scheduler.add_job(
                func=self.cleanup_old_assets,
                trigger=CronTrigger(hour=2, minute=0),  # Run daily at 2 AM
                id='drive_cleanup_daily',
                name='Drive Assets Cleanup (Daily)',
                replace_existing=True
            )
            
            self.scheduler.start()
            print("✅ Drive sync scheduler started")
    
    def stop_scheduler(self):
        """Stop the background scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("🛑 Drive sync scheduler stopped")
    
    def sync_all_projects(self):
        """Sync all projects that have Google Drive integrations."""
        try:
            print("🔄 Starting scheduled Google Drive sync...")
            
            # Get all projects with Google Drive integrations
            integrations = self.sql_db.supabase_client.table('project_integrations')\
                .select('course_name, provider')\
                .eq('provider', 'google_drive')\
                .execute()
            
            if not integrations.data:
                print("📭 No Google Drive integrations found")
                return
            
            synced_count = 0
            for integration in integrations.data:
                try:
                    course_name = integration['course_name']
                    print(f"🔄 Syncing course: {course_name}")
                    
                    # Trigger sync for this project
                    self.drive_service._sync_items(course_name)
                    synced_count += 1
                    
                except Exception as e:
                    print(f"❌ Error syncing course {integration['course_name']}: {e}")
                    continue
            
            print(f"✅ Completed scheduled sync for {synced_count} projects")
            
        except Exception as e:
            print(f"❌ Error in scheduled sync: {e}")
    
    def cleanup_old_assets(self):
        """Clean up old ingestion assets to prevent database bloat."""
        try:
            print("🧹 Starting drive assets cleanup...")
            
            # Delete assets older than 30 days with failed status
            cutoff_date = datetime.utcnow() - timedelta(days=30)
            
            result = self.sql_db.supabase_client.table('ingestion_assets')\
                .delete()\
                .eq('status', 'failed')\
                .eq('provider', 'google_drive')\
                .lt('created_at', cutoff_date.isoformat())\
                .execute()
            
            deleted_count = len(result.data) if result.data else 0
            print(f"🗑️ Cleaned up {deleted_count} old failed ingestion records")
            
        except Exception as e:
            print(f"❌ Error in cleanup: {e}")
    
    def sync_project_now(self, course_name: str):
        """Manually trigger sync for a specific project."""
        try:
            print(f"🔄 Manual sync triggered for course: {course_name}")
            self.drive_service._sync_items(course_name)
            print(f"✅ Manual sync completed for course: {course_name}")
        except Exception as e:
            print(f"❌ Error in manual sync for {course_name}: {e}")
            raise


# Global scheduler instance
drive_sync_scheduler = None


def initialize_scheduler(sql_db: SQLDatabase, drive_service: GoogleDriveService):
    """Initialize the global scheduler."""
    global drive_sync_scheduler
    
    # Only initialize if enabled
    if os.environ.get('ENABLE_DRIVE_SYNC_SCHEDULER', 'true').lower() == 'true':
        drive_sync_scheduler = DriveSync(sql_db, drive_service)
        drive_sync_scheduler.start_scheduler()
    else:
        print("📴 Drive sync scheduler disabled")


def shutdown_scheduler():
    """Shutdown the global scheduler."""
    global drive_sync_scheduler
    if drive_sync_scheduler:
        drive_sync_scheduler.stop_scheduler()
        drive_sync_scheduler = None
