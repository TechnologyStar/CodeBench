# CodeBench — Framework d'évaluation d'agents de codage IA

Un framework léger, orienté API, pour évaluer les agents de codage IA (Claude Code, OpenAI Codex, etc.) avec exécution de code en bac à sable, détection de bugs et interface Web intégrée.

Construit sur [OpenCompass](https://github.com/open-compass/opencompass) par le [Laboratoire d'Intelligence Artificielle de Shanghai](https://www.shlab.org.cn/). Ce projet étend l'infrastructure d'évaluation originale avec des workflows d'agents de codage modernes, l'exécution en bac à sable et un serveur API simplifié.

[中文](README_zh.md) | [English](README.md) | [日本語](README_ja.md) | [Русский](README_ru.md) | Français

## Fonctionnalités

- **Support multi-fournisseurs** — Claude API, Gemini API, OpenAI Responses API, OpenAI Chat Completions
- **Wrappers d'agents de codage** — Évaluation d'agents plug-and-play (Claude Code, Codex, personnalisés)
- **Exécution en bac à sable** — Isolation par sous-processus et Docker avec limites de temps et mémoire
- **Détection de bugs** — Correspondance de motifs d'erreur par expressions régulières avec classification de sévérité et suggestions de correction
- **Gestion des tâches** — Pause/reprise/retry avec récupération par points de contrôle
- **API REST** — Serveur HTTP léger (bibliothèque standard uniquement, zéro dépendance supplémentaire)
- **Interface Web** — Tableau de bord en thème sombre optionnel (`--enable-ui`)
- **Tests complets** — 30+ tests unitaires

## Démarrage rapide

```bash
# Installation des dépendances (uniquement pour les intégrations API d'agents)
pip install anthropic google-generativeai openai

# Démarrer le serveur API
python -m opencompass.server --port 8000

# Avec l'interface Web activée
python -m opencompass.server --port 8000 --enable-ui
```

## Points d'accès API

| Méthode | Point d'accès | Description |
|---------|---------------|-------------|
| GET | `/api/v1/health` | Vérification de santé |
| GET | `/api/v1/models` | Lister les modèles disponibles |
| POST | `/api/v1/evaluate` | Soumettre une évaluation de modèle |
| POST | `/api/v1/agent/evaluate` | Soumettre une évaluation d'agent |
| POST | `/api/v1/sandbox/execute` | Exécuter du code en bac à sable |
| GET | `/api/v1/tasks/{id}` | Consulter le statut d'une tâche |
| POST | `/api/v1/tasks/{id}/pause` | Mettre en pause une tâche |
| POST | `/api/v1/tasks/{id}/resume` | Reprendre une tâche en pause |
| POST | `/api/v1/tasks/{id}/retry` | Réessayer une tâche échouée |
| GET | `/api/v1/tasks/{id}/bugs` | Obtenir le rapport de détection de bugs |
| GET | `/` | Interface Web (avec `--enable-ui`) |

## Tests

```bash
python -m pytest tests/test_sandbox.py tests/test_agents.py -v
```

## Remerciements

Ce projet est construit sur [OpenCompass](https://github.com/open-compass/opencompass), un framework d'évaluation open source développé par le [Laboratoire d'Intelligence Artificielle de Shanghai](https://www.shlab.org.cn/). Nous adressons nos sincères remerciements à l'équipe OpenCompass pour leur travail fondateur dans l'infrastructure d'évaluation de LLM.

## Licence

Apache License 2.0 — Voir [LICENSE](LICENSE) pour les détails.
