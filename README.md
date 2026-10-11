# inplay-watchlist
每日美股 in-play 睇盤清單(人手輔助,非買賣信號):升跌幅/量比排名 + SEC EDGAR 事件標籤 + 日線結構,分 A 強勢 / B 超跌 / C 避開 / D 其他。
GitHub Actions 每個交易日收市後自動更新,發佈到 GitHub Pages。本地:`python watchlist.py --refresh`。
研究結論:新聞 gap 追入扣成本後冇穩定 edge,只用嚟縮窄要睇嘅股票。
