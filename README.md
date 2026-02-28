# exvs2ib-vsmobile-scraper

機動戦士ガンダム エクストリームバーサス2 インフィニットブースト（EXVS2IB）のポータルサイト「VS.モバイル」から**店内対戦戦績**データを自動取得するツール。

公式アプリでは店内対戦の詳細履歴（試合ごとのスコア・タイムライン等）を管理していないため、VS.モバイルの店内対戦戦績ページ（`/results/shop/`）をスクレイピングして JSON として出力する。

## 必要環境

- Python 3.10 以上
- pip

## セットアップ

```bash
pip install -r requirements.txt
cp cookies.json.example cookies/cookies.json
```

`cookies/cookies.json` にブラウザからエクスポートした VS.モバイルのセッション Cookie を記入する（後述）。

## Cookie の準備

1. ブラウザで VS.モバイル（`web.vsmobile.jp`）にログインする
2. EditThisCookie 等のブラウザ拡張でクッキーを JSON 形式でエクスポートする
3. エクスポートした JSON を `cookies/{ユーザー名}.json` として `cookies/` ディレクトリに保存する

`cookies/` ディレクトリは `.gitignore` 対象（JSON ファイルのみ）のため、誤ってコミットされない。

Cookie ファイルのフォーマット（EditThisCookie 形式）:

```json
[
  {
    "name": "_session_id",
    "value": "your-session-value-here",
    "domain": "web.vsmobile.jp"
  }
]
```

## 使い方

```bash
python scrape.py
```

### オプション

| オプション | デフォルト | 説明 |
|-----------|-----------|------|
| `--cookies` | `cookies/cookies.json` | Cookie ファイルのパス（単一ユーザー） |
| `--cookies-all [PATH]` | `cookies_all.json` | 全ユーザー一括実行モード（後述） |
| `--output` | `output/{プレイヤー名}_{日付}.json` | 出力ファイルのパス |

### 実行例

```bash
# デフォルト設定で実行（cookies.json を使用）
python scrape.py

# Cookie ファイルと出力先を指定
python scrape.py --cookies cookies/alice.json --output alice_20260214.json
```

### 複数ユーザーの一括実行

各ユーザーの Cookie を `cookies/{ユーザー名}.json` として `cookies/` ディレクトリに配置した後、`build_cookies.py` で一括管理ファイルを生成する。

```bash
# 1. cookies/*.json を自動検出して cookies/all.json を生成
python build_cookies.py

# 2. 全ユーザー分を一括スクレイピング・マージして出力
python scrape.py --cookies-all
```

`--cookies-all` モードでは、全ユーザーの結果を `match_ts` キーで重複排除してマージする。出力ファイル名のデフォルトは `output/all_{YYYYMMDD}.json`。

いずれかのユーザーの Cookie が期限切れだった場合はそのユーザーをスキップして処理を継続し、最後に警告を表示して終了コード `1` で終了する。

## 出力形式

出力ファイル名（デフォルト）: `output/{プレイヤー名}_{YYYYMMDD}.json`

試合データのリスト（`match_ts` 昇順）を JSON で出力する。

```json
[
  {
    "match_ts": "1739500000",
    "time": "14:32",
    "game_date": "2026/02/14(土)",
    "shop_name": "〇〇ゲームセンター",
    "team_a": {
      "team_name": "チームA",
      "result": "win",
      "players": [
        {
          "name": "プレイヤー1",
          "player_param": "AbCdEfGh...",
          "icon_url": "https://example.com/icon.png",
          "mastery": "blue5",
          "prefecture": "東京都",
          "is_self": true,
          "match_rank": 1,
          "score": 12000,
          "kills": 3,
          "deaths": 1,
          "damage_dealt": 8500,
          "damage_received": 3200,
          "exburst_damage": 1500
        }
      ]
    },
    "team_b": { "...": "..." },
    "timeline_raw": {
      "groups": {
        "team1-1": "https://example.com/unit_icon.png"
      },
      "events": [
        {
          "group": "team1-1",
          "start_cs": 1500,
          "start_str": "0:15.00",
          "end_cs": 4200,
          "end_str": "0:42.00",
          "class_name": "exbst-s",
          "is_point": false
        }
      ],
      "game_end_cs": 36000,
      "game_end_str": "6:00.00"
    }
  }
]
```

### フィールド説明

**プレイヤー:**

| フィールド | 説明 |
|-----------|------|
| `player_param` | プロフィール URL の `param` 値（プレイヤー識別子） |
| `icon_url` | 使用機体のアイコン URL |
| `mastery` | 習熟度クラス（例: `blue5`, `red3`） |
| `prefecture` | 都道府県 |
| `is_self` | Cookie のプレイヤー自身かどうか |
| `match_rank` | 試合内順位（1〜4） |

**タイムライン (`timeline_raw`):**

| フィールド | 説明 |
|-----------|------|
| `groups` | グループID → 機体アイコン URL のマップ |
| `events` | イベントリスト（EXバースト・被撃墜など） |
| `game_end_cs` | 試合終了時刻（センチ秒） |
| `game_end_str` | 試合終了時刻（`M:SS.CC` 形式） |

タイムラインの `class_name` 主な値:

| 値 | 意味 |
|----|------|
| `ex` | EXバースト発動可能域 |
| `exbst-f` | ファイティングバースト発動中 |
| `exbst-s` | シューティングバースト発動中 |
| `exbst-e` | エクステンドバースト発動中 |
| `ov` | EXオーバーリミット発動可能域 |
| `exbst-ov` | EXオーバーリミット発動中 |
| `xb` | EXバーストクロス |
| `is_point: true` | 被撃墜 |
| `com` | データ無し |

時刻の単位はセンチ秒（cs）: `new Date(0, 0, 0, A, B, C)` → `A*6000 + B*100 + C` cs

## GitHub Actions による自動実行

### 概要

`.github/workflows/scrape.yml` ワークフローを使うと、ローカル環境を一切触らずにスクレイピング〜API 送信を一括実行できる。

### 必要な GitHub Secrets

リポジトリの **Settings → Secrets and variables → Actions** に以下の 3 つを登録する。

| シークレット名 | 内容 |
|---------------|------|
| `COOKIES_ALL` | `cookies/all.json` の中身をそのまま貼り付けた JSON 文字列 |
| `VSMOBILE_API_TOKEN` | vsmobile-kgy の API Bearer トークン |
| `VSMOBILE_API_URL` | vsmobile-kgy のベース URL（例: `https://example.com`、末尾スラッシュなし） |

#### `COOKIES_ALL` の形式

`python build_cookies.py` で生成される `cookies/all.json` の内容をそのまま貼り付ける。

```json
{
  "ぱぴこ": [{ "name": "_session_id", "value": "...", "domain": "web.vsmobile.jp" }],
  "てるしき": [{ "name": "_session_id", "value": "...", "domain": "web.vsmobile.jp" }]
}
```

### 手動実行手順

1. GitHub リポジトリの **Actions** タブを開く
2. 左メニューから **Scrape and Upload Stats** を選択
3. **Run workflow** ボタンをクリック
4. `event_id` に vsmobile-kgy のイベント ID を入力して実行

### エラー時の動作

| 状況 | 挙動 |
|------|------|
| Cookie が期限切れ | スクレイパーが終了コード 1 で終了し、`POST /api/events/{id}/notify_failure` にエラーメッセージを送信 |
| API 送信失敗（4xx/5xx） | `POST /api/events/{id}/notify_failure` にエラーメッセージを送信 |
| その他のエラー | 同上 |

いずれの場合も Actions のログ URL がエラーメッセージに含まれる。
