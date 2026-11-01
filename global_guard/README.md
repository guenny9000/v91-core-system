# V91 Global Guard

Standalone, provider-neutral policy middleware for AI-agent tool calls. Python standard library only.

Default stance: deny unknown capabilities; no network, model changes, production changes, or self-propagation.

Run tests:

    python -m unittest discover -s tests -p "test_global_guard*.py" -v

Read the full boundary and integration notes in ../docs/V91_GLOBAL_GUARD.md. This is an isolated test component, not a global deployment or production certification.
