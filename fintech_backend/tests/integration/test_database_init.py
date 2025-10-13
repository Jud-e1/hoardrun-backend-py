"""
Integration tests for database initialization script.
"""

import pytest
import os
import tempfile
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add the scripts directory to the path for importing
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from init_database import (
    check_database, run_migrations, create_sample_data, 
    reset_database, main
)


class TestDatabaseInitScript:
    """Test database initialization script functions."""
    
    def test_check_database_success(self):
        """Test database check function when database is healthy."""
        with patch('init_database.check_database_connection') as mock_check:
            with patch('init_database.get_database_info') as mock_info:
                mock_check.return_value = True
                mock_info.return_value = {
                    "database_url": "sqlite:///test.db",
                    "database_version": "SQLite 3.x",
                    "pool_info": {"pool_size": 5}
                }
                
                result = check_database()
                assert result is True
                mock_check.assert_called_once()
                mock_info.assert_called_once()
    
    def test_check_database_failure(self):
        """Test database check function when database is unhealthy."""
        with patch('init_database.check_database_connection') as mock_check:
            mock_check.return_value = False
            
            result = check_database()
            assert result is False
            mock_check.assert_called_once()
    
    def test_run_migrations_success(self):
        """Test running migrations successfully."""
        with patch('init_database.Path') as mock_path:
            with patch('init_database.Config') as mock_config:
                with patch('init_database.command') as mock_command:
                    # Mock path exists
                    mock_path_instance = MagicMock()
                    mock_path_instance.exists.return_value = True
                    mock_path.return_value.parent.parent = mock_path_instance
                    mock_path_instance.__truediv__ = lambda self, other: mock_path_instance
                    
                    result = run_migrations()
                    assert result is True
                    mock_command.upgrade.assert_called_once()
    
    def test_run_migrations_no_config(self):
        """Test running migrations when alembic.ini doesn't exist."""
        with patch('init_database.Path') as mock_path:
            # Mock path doesn't exist
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path.return_value.parent.parent = mock_path_instance
            mock_path_instance.__truediv__ = lambda self, other: mock_path_instance
            
            result = run_migrations()
            assert result is False
    
    def test_run_migrations_exception(self):
        """Test running migrations when an exception occurs."""
        with patch('init_database.Path') as mock_path:
            with patch('init_database.Config') as mock_config:
                with patch('init_database.command') as mock_command:
                    # Mock path exists
                    mock_path_instance = MagicMock()
                    mock_path_instance.exists.return_value = True
                    mock_path.return_value.parent.parent = mock_path_instance
                    mock_path_instance.__truediv__ = lambda self, other: mock_path_instance
                    
                    # Mock command raises exception
                    mock_command.upgrade.side_effect = Exception("Migration failed")
                    
                    result = run_migrations()
                    assert result is False
    
    def test_create_sample_data_success(self):
        """Test creating sample data successfully."""
        with patch('init_database.SessionLocal') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Mock no existing user
            mock_session.query.return_value.filter.return_value.first.return_value = None
            
            result = create_sample_data()
            assert result is True
            mock_session.add.assert_called()
            mock_session.commit.assert_called()
    
    def test_create_sample_data_already_exists(self):
        """Test creating sample data when it already exists."""
        with patch('init_database.SessionLocal') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Mock existing user
            mock_user = MagicMock()
            mock_session.query.return_value.filter.return_value.first.return_value = mock_user
            
            result = create_sample_data()
            assert result is True
            # Should not add new data
            mock_session.add.assert_not_called()
    
    def test_create_sample_data_exception(self):
        """Test creating sample data when an exception occurs."""
        with patch('init_database.SessionLocal') as mock_session_class:
            mock_session = MagicMock()
            mock_session_class.return_value = mock_session
            
            # Mock exception
            mock_session.query.side_effect = Exception("Database error")
            
            result = create_sample_data()
            assert result is False
    
    def test_reset_database_success(self):
        """Test resetting database successfully."""
        with patch('init_database.drop_tables') as mock_drop:
            with patch('init_database.create_tables') as mock_create:
                result = reset_database()
                assert result is True
                mock_drop.assert_called_once()
                mock_create.assert_called_once()
    
    def test_reset_database_exception(self):
        """Test resetting database when an exception occurs."""
        with patch('init_database.drop_tables') as mock_drop:
            mock_drop.side_effect = Exception("Drop failed")
            
            result = reset_database()
            assert result is False


class TestDatabaseInitScriptCLI:
    """Test database initialization script command line interface."""
    
    def test_main_check_only(self):
        """Test main function with --check-only flag."""
        with patch('init_database.check_database') as mock_check:
            with patch('sys.argv', ['init_database.py', '--check-only']):
                mock_check.return_value = True
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 0
                mock_check.assert_called_once()
    
    def test_main_check_only_failure(self):
        """Test main function with --check-only flag when check fails."""
        with patch('init_database.check_database') as mock_check:
            with patch('sys.argv', ['init_database.py', '--check-only']):
                mock_check.return_value = False
                
                with pytest.raises(SystemExit) as exc_info:
                    main()
                
                assert exc_info.value.code == 1
                mock_check.assert_called_once()
    
    def test_main_force_reset_production(self):
        """Test main function with --force-reset in production environment."""
        with patch('init_database.check_database') as mock_check:
            with patch('init_database.get_settings') as mock_settings:
                with patch('sys.argv', ['init_database.py', '--force-reset']):
                    mock_check.return_value = True
                    mock_settings.return_value.environment = "production"
                    
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    
                    assert exc_info.value.code == 1
    
    def test_main_force_reset_cancelled(self):
        """Test main function with --force-reset when user cancels."""
        with patch('init_database.check_database') as mock_check:
            with patch('init_database.get_settings') as mock_settings:
                with patch('builtins.input') as mock_input:
                    with patch('sys.argv', ['init_database.py', '--force-reset']):
                        mock_check.return_value = True
                        mock_settings.return_value.environment = "development"
                        mock_input.return_value = "no"
                        
                        with pytest.raises(SystemExit) as exc_info:
                            main()
                        
                        assert exc_info.value.code == 0
    
    def test_main_success_flow(self):
        """Test main function successful execution flow."""
        with patch('init_database.check_database') as mock_check:
            with patch('init_database.run_migrations') as mock_migrate:
                with patch('sys.argv', ['init_database.py']):
                    mock_check.return_value = True
                    mock_migrate.return_value = True
                    
                    # Should complete without raising SystemExit
                    main()
                    
                    mock_check.assert_called_once()
                    mock_migrate.assert_called_once()
    
    def test_main_migration_failure(self):
        """Test main function when migration fails."""
        with patch('init_database.check_database') as mock_check:
            with patch('init_database.run_migrations') as mock_migrate:
                with patch('sys.argv', ['init_database.py']):
                    mock_check.return_value = True
                    mock_migrate.return_value = False
                    
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    
                    assert exc_info.value.code == 1
    
    def test_main_with_sample_data(self):
        """Test main function with --create-sample-data flag."""
        with patch('init_database.check_database') as mock_check:
            with patch('init_database.run_migrations') as mock_migrate:
                with patch('init_database.create_sample_data') as mock_sample:
                    with patch('sys.argv', ['init_database.py', '--create-sample-data']):
                        mock_check.return_value = True
                        mock_migrate.return_value = True
                        mock_sample.return_value = True
                        
                        main()
                        
                        mock_check.assert_called_once()
                        mock_migrate.assert_called_once()
                        mock_sample.assert_called_once()
    
    def test_main_verbose_logging(self):
        """Test main function with --verbose flag."""
        with patch('init_database.check_database') as mock_check:
            with patch('init_database.run_migrations') as mock_migrate:
                with patch('logging.getLogger') as mock_logger:
                    with patch('sys.argv', ['init_database.py', '--verbose']):
                        mock_check.return_value = True
                        mock_migrate.return_value = True
                        
                        main()
                        
                        # Should set debug level
                        mock_logger.return_value.setLevel.assert_called()


class TestDatabaseInitScriptIntegration:
    """Integration tests for database initialization script."""
    
    @pytest.mark.slow
    def test_script_execution(self):
        """Test that the script can be executed without errors."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_database.py"
        
        # Test --check-only flag
        result = subprocess.run([
            sys.executable, str(script_path), "--check-only"
        ], capture_output=True, text=True)
        
        # Should exit with 0 or 1 (depending on database availability)
        assert result.returncode in [0, 1]
    
    def test_help_output(self):
        """Test that the script shows help when requested."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "init_database.py"
        
        result = subprocess.run([
            sys.executable, str(script_path), "--help"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "Database initialization script" in result.stdout
