<!-- markdownlint-disable MD033 MD041 -->
<p align="center">
  <img alt="LOGO" src="icon.png" width="256" height="256" />
</p>

<div align="center">

# MAH

新しいアーキテクチャに基づく 東京放課後サモナーズ（Housamo） 自動戦闘/周回 アシスタント。画像認識技術＋シミュレーション操作で両手を解放しよう！
[MaaFramework](https://github.com/MaaXYZ/MaaFramework) によって強力に駆動されています！

🌟本プロジェクトを気に入っていただけましたら、リポジトリの右上の星をクリックしてください🌟

**[简体中文](README.md) | [繁體中文](README_tw.md) | [English](README_en.md) | 日本語**

</div>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white">
  <img alt="platform" src="https://img.shields.io/badge/platform-Windows-blueviolet">
  
## 機能リスト

- **ゲーム起動**：ゲームを自動的に起動し、メイン画面に入るまで待機します。
- **ダンジョン戦闘**：
  - すべての常設ダンジョンおよびイベントダンジョンの周回をサポートします。
  - 挑戦回数をカスタマイズ可能で、自動的にスタミナ回復アイテム（ランタン）を使用し DP を回復します。
  - インテリジェントなサポート選択（特定のキャラクター、AR、ステータス/シードによる最強サポートのスクリーニング）。
  - 自動戦闘スクリプトの柔軟な JSON 設定とカスタム編成をサポートします。
- **スタミナ消費戦闘**：
  - 14章の花クエストおよび常設デイリークエストをサポートします。
  - 優先順位（全->半->微）に従ってスタミナ回復薬を自動的に使用します。
- **報酬受け取り**：ウィークリーミッションおよびプレゼントボックスの報酬を自動的に受け取ります。

## 取扱説明書

- [ご案内 (初心者は必ずお読みください)](./assets/docs/ja_jp/welcome.md) - 設定および起動の方法を早く理解する
- [自動戦闘 JSON 設定仕様](./docs/ja_jp/自動戦闘json配置.md) - 戦闘スクリプトおよび編成を深くカスタマイズする

このリポジトリで関連する質問をしてください。ログがある場合は、できればそれも添付してください（`debug/maa.log` ファイル）。

## 開発関連

本プロジェクトのコアは [MaaFramework](https://github.com/MaaXYZ/MaaFramework) をベースに開発されています。
二次開発の需要がある場合は、MaaFramework の関連ドキュメントを参照してください。

## 謝辞

本プロジェクトは **[MaaFramework](https://github.com/MaaXYZ/MaaFramework)** によって強力に駆動されています！

アイコンサポート：アイコンを提供してくださった [喝茶先知](https://twitter.com/hechaxianzhi) に感謝します。

~~もしこのアイコンの枠が醜いと思ったら、私を叱ってください。枠は自分で作ったものです。~~

### 貢献者一覧

本プロジェクトに貢献してくださった以下の開発者に感謝します:

[![Contributors](https://contrib.rocks/image?repo=Quartewe/MAH&max=1000)](https://github.com/Quartewe/MAH/graphs/contributors)

## 私たちに参加する

- 関連する質問がある場合は、まずGitHubのissueセクションに投稿してください

- メール<quarty1015@gmail.com>で私に連絡することができます
