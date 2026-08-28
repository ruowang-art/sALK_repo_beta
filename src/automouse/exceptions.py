class AutoMouseError(Exception):
    """Base class for expected, user-facing AutoMouse failures."""


class ConfigurationError(AutoMouseError):
    pass


class InputValidationError(AutoMouseError):
    pass


class DuplicateInputError(AutoMouseError):
    pass


class RTranslationError(AutoMouseError):
    pass


class TranslationValidationError(AutoMouseError):
    pass


class InventoryValidationError(AutoMouseError):
    pass


class InventoryUpdateError(AutoMouseError):
    pass


class CageCardTemplateError(AutoMouseError):
    pass


class CageCardGenerationError(AutoMouseError):
    pass

