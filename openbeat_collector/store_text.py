"""UI strings for the pack store (kept separate from the core i18n module).

Selected by OPENBEAT_LANG (en default, ja for Japanese), mirroring rwt.i18n.
"""
from __future__ import annotations

import os

_EN = {
    "store_title": "Pack Store",
    "store_intro": "Beat packs add a journalist specialty (a theme + a curated source list) to the toolkit. The core tool is free and open source; some packs are paid add-ons.",
    "back_to_collect": "← Back to collection",
    "tier_label": "Your plan",
    "tier_free": "Free",
    "tier_pro": "Pro",
    "tier_free_note": "Free plan: one active pack at a time.",
    "tier_pro_note": "Pro plan: use multiple packs at once.",
    "active_count": "Active packs: {n}",
    "active_count_limited": "Active packs: {n} / {limit}",
    "free_badge": "Free",
    "paid_badge": "Paid",
    "price_free": "Free",
    "price_paid": "¥{price} / year",
    "owned_badge": "Owned",
    "active_badge": "Active",
    "btn_use": "Use this pack",
    "btn_switch": "Switch to this pack",
    "btn_add": "Add (use together)",
    "btn_deactivate": "Stop using",
    "btn_buy": "Buy / details",
    "sources_n": "{n} sources",
    "verified": "JASTJ verified",
    "community": "Community",
    "license_h": "Unlock paid packs",
    "license_note": "Bought a pack or Pro on the store? Paste your license key here to unlock it.",
    "license_ph": "License key (e.g. OPENBEAT-XXXX-XXXX)",
    "license_btn": "Activate key",
    "license_clear": "Remove license",
    "license_have": "License active ({tier}). Unlocked: {packs}",
    "buy_more_h": "Get more",
    "pro_upsell": "Upgrade to Pro to use several packs at the same time, like the sections of a newspaper.",
    "buy_pack_note": "Paid packs are sold on OpenBeat Market. After purchase you receive a license key to paste above.",
    # flashes
    "f_need_pro": "The free plan allows one active pack at a time. Activating this replaced your previous pack. Upgrade to Pro to use several at once.",
    "f_activated": "Activated: {name}",
    "f_deactivated": "Stopped using: {name}",
    "f_not_entitled": "This is a paid pack. Buy it on the store and activate your license key to unlock it.",
    "f_install_failed": "Could not download this pack ({err}). Check your connection or try again.",
    "f_license_ok": "License activated ({tier}). Unlocked: {packs}",
    "f_license_bad": "That license key was not recognized. Check the key from your purchase confirmation.",
    "f_license_empty": "Enter a license key.",
    "f_license_cleared": "License removed. Paid packs are locked again.",
    "f_index_refreshed": "Store catalog refreshed.",
    "refresh_btn": "Refresh catalog",
}

_JA = {
    "store_title": "パックストア",
    "store_intro": "ビートパックは、ジャーナリストの専門領域（テーマ＋厳選した情報源）をツールに追加します。ツール本体は無料・オープンソースで、一部のパックは有料の追加機能です。",
    "back_to_collect": "← 収集に戻る",
    "tier_label": "ご利用プラン",
    "tier_free": "無料",
    "tier_pro": "Pro",
    "tier_free_note": "無料プラン：同時に使えるパックは1つまで。",
    "tier_pro_note": "Pro プラン：複数のパックを同時に使えます。",
    "active_count": "有効なパック：{n}",
    "active_count_limited": "有効なパック：{n} / {limit}",
    "free_badge": "無料",
    "paid_badge": "有料",
    "price_free": "無料",
    "price_paid": "年額 ¥{price}",
    "owned_badge": "購入済",
    "active_badge": "使用中",
    "btn_use": "このパックを使う",
    "btn_switch": "このパックに切り替え",
    "btn_add": "追加（一緒に使う）",
    "btn_deactivate": "使用をやめる",
    "btn_buy": "購入・詳細",
    "sources_n": "情報源 {n} 件",
    "verified": "JASTJ 検証済み",
    "community": "コミュニティ",
    "license_h": "有料パックを解錠",
    "license_note": "ストアでパックまたは Pro を購入した方は、ライセンスキーをここに貼り付けて解錠してください。",
    "license_ph": "ライセンスキー（例 OPENBEAT-XXXX-XXXX）",
    "license_btn": "キーを適用",
    "license_clear": "ライセンスを削除",
    "license_have": "ライセンス有効（{tier}）。解錠済：{packs}",
    "buy_more_h": "さらに追加",
    "pro_upsell": "Pro にアップグレードすると、新聞の各面のように複数のパックを同時に使えます。",
    "buy_pack_note": "有料パックは OpenBeat Market で販売しています。購入後に発行されるライセンスキーを上記に貼り付けてください。",
    "f_need_pro": "無料プランでは同時に使えるパックは1つまでです。今回の有効化で以前のパックは入れ替わりました。複数を同時に使うには Pro にアップグレードしてください。",
    "f_activated": "有効化しました：{name}",
    "f_deactivated": "使用をやめました：{name}",
    "f_not_entitled": "これは有料パックです。ストアで購入し、ライセンスキーを適用すると解錠されます。",
    "f_install_failed": "パックをダウンロードできませんでした（{err}）。接続を確認して再試行してください。",
    "f_license_ok": "ライセンスを適用しました（{tier}）。解錠：{packs}",
    "f_license_bad": "ライセンスキーを認識できませんでした。購入確認のキーをご確認ください。",
    "f_license_empty": "ライセンスキーを入力してください。",
    "f_license_cleared": "ライセンスを削除しました。有料パックは再びロックされます。",
    "f_index_refreshed": "ストアのカタログを更新しました。",
    "refresh_btn": "カタログを更新",
}


def get_lang() -> str:
    return "ja" if (os.environ.get("OPENBEAT_LANG", "en").lower().startswith("ja")) else "en"


def store_strings() -> dict:
    return _JA if get_lang() == "ja" else _EN
