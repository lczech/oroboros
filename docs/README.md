# Docs

This directory holds lightweight project documentation while Oroboros is still
in active design and implementation.

The goal here is not polished end-user documentation yet. Instead, these notes
capture how the current architecture is intended to work so we do not lose the
reasoning behind the model and parser as the code evolves.

Current notes:

- [Model Navigation](./model-navigation.md)
- [Parse Pipeline](./parse-pipeline.md)
- [Customization Workflow](./customization-workflow.md)

The header workflow is now intentionally layered above parsing:

- discover known project headers
- optionally apply activation selection
- parse one `HeaderSelection`

Once the public API and the parse/translate/emit pipeline have settled more,
this folder can either grow into a proper documentation site or feed into one.
