from .subprocess_sandbox import SubprocessSandbox
from .docker_sandbox import DockerSandbox
from .result import SandboxResult


def create_sandbox(type='subprocess', **kwargs):
    """Factory function for creating sandbox instances.

    Args:
        type: Sandbox type, 'subprocess' or 'docker'.
        **kwargs: Arguments passed to the sandbox constructor.

    Returns:
        Sandbox instance.

    Raises:
        ValueError: If the sandbox type is unknown.
    """
    if type == 'subprocess':
        return SubprocessSandbox(**kwargs)
    elif type == 'docker':
        return DockerSandbox(**kwargs)
    else:
        raise ValueError(f'Unknown sandbox type: {type}')
