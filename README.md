# NeboLoop Roles

Official roles for the NeboLoop AI agent platform. Each role bundles a persona, automated workflows, and skill dependencies.

## Structure

Each role is a directory containing:

```
role-name/
├── ROLE.md           # Persona (becomes system prompt)
├── role.json         # Workflows + triggers + inputs + skill dependencies
└── manifest.json     # Marketplace metadata
```

## License

Apache-2.0
