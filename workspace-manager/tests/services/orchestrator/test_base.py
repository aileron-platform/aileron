import pytest
from unittest.mock import Mock, patch
from app.services.orchestrator.factory import OrchestratorFactory

class TestOrchestratorFactory:
    @patch('app.services.orchestrator.factory.get_settings')
    def test_get_docker_orchestrator(self, mock_get_settings):
        mock_settings = Mock()
        mock_settings.RUNTIME_PROVISIONER = "docker"
        mock_get_settings.return_value = mock_settings
        mock_instance = Mock()

        with patch.dict(
            OrchestratorFactory._orchestrators,
            {"docker": Mock(return_value=mock_instance)},
            clear=False,
        ):
            orchestrator = OrchestratorFactory.get_orchestrator()
        assert orchestrator is mock_instance

    @patch('app.services.orchestrator.factory.get_settings')
    def test_get_k8s_orchestrator_raises_error(self, mock_get_settings):
        # K8s orchestrator raises NotImplementedError on init
        mock_settings = Mock()
        mock_settings.RUNTIME_PROVISIONER = "kubernetes"
        mock_get_settings.return_value = mock_settings

        with pytest.raises(NotImplementedError):
            OrchestratorFactory.get_orchestrator()

    @patch('app.services.orchestrator.factory.get_settings')
    def test_unknown_orchestrator_raises_error(self, mock_get_settings):
        mock_settings = Mock()
        mock_settings.RUNTIME_PROVISIONER = "unknown"
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError):
            OrchestratorFactory.get_orchestrator()
