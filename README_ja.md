# CodeBench — AI コーディングエージェント評価フレームワーク

サンドボックス化されたコード実行、バグ検出、組み込み Web UI を備えた、軽量で API ファーストな AI コーディングエージェント評価フレームワーク。

[上海人工知能ラボラトリー](https://www.shlab.org.cn/)による [OpenCompass](https://github.com/open-compass/opencompass)をベースに構築。このプロジェクトは、元の評価インフラストラクチャを拡張し、モダンなコーディングエージェントワークフロー、サンドボックス実行、効率的な API サーバーを提供します。

[中文](README_zh.md) | [English](README.md) | 日本語 | [Русский](README_ru.md) | [Français](README_fr.md)

## 特徴

- **マルチプロバイダー対応** — Claude API、Gemini API、OpenAI Responses API、OpenAI Chat Completions
- **コーディングエージェントラッパー** — プラガブルなエージェント評価（Claude Code、Codex、カスタム）
- **サンドボックス実行** — タイムアウト・メモリ制限付きのサブプロセス・Docker 分離
- **バグ検出** — 正規表現ベースのエラーパターンマッチング、重要度分類、修正提案
- **タスク管理** — チェックポイント付きの一時停止/再開/リトライ
- **REST API** — 軽量 HTTP サーバー（標準ライブラリのみ、追加依存なし）
- **Web UI** — オプションのダークテーマダッシュボード（`--enable-ui`）
- **包括的なテスト** — 30以上のユニットテスト

## クイックスタート

```bash
# 依存関係のインストール（エージェント API 統合のみ必要）
pip install anthropic google-generativeai openai

# API サーバーを起動
python -m opencompass.server --port 8000

# Web UI を有効にする場合
python -m opencompass.server --port 8000 --enable-ui
```

## API エンドポイント

| メソッド | エンドポイント | 説明 |
|----------|---------------|------|
| GET | `/api/v1/health` | ヘルスチェック |
| GET | `/api/v1/models` | 利用可能なモデル一覧 |
| POST | `/api/v1/evaluate` | モデル評価を送信 |
| POST | `/api/v1/agent/evaluate` | コーディングエージェント評価を送信 |
| POST | `/api/v1/sandbox/execute` | サンドボックスでコードを実行 |
| GET | `/api/v1/tasks/{id}` | タスク状態を照会 |
| POST | `/api/v1/tasks/{id}/pause` | 実行中のタスクを一時停止 |
| POST | `/api/v1/tasks/{id}/resume` | 一時停止中のタスクを再開 |
| POST | `/api/v1/tasks/{id}/retry` | 失敗したタスクをリトライ |
| GET | `/api/v1/tasks/{id}/bugs` | バグ検出レポートを取得 |
| GET | `/` | Web UI（`--enable-ui` 時） |

## テスト

```bash
python -m pytest tests/test_sandbox.py tests/test_agents.py -v
```

## 謝辞

本プロジェクトは [OpenCompass](https://github.com/open-compass/opencompass)、[上海人工知能ラボラトリー](https://www.shlab.org.cn/)によるオープンソース評価フレームワークをベースに構築されています。LLM 評価インフラストラクチャにおける OpenCompass チームの基盤的な貢献に深く感謝します。

## ライセンス

Apache License 2.0 — 詳細は [LICENSE](LICENSE) を参照。
