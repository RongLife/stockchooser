# 借券強勢股雷達

用臺灣證券交易所公開資料篩選上市股：借券賣出比、回補天數、投信／外資買超、營收年增率，條件可在網頁上即時調整。

## 怎麼更新

- **自動**：GitHub Actions 每天台北時間 21:30 抓資料並重新發布網站（`.github/workflows/update.yml`）。
- **網頁上手動**：任何人按右上角「更新到最新收盤」，瀏覽器會直接向證交所抓網站還沒有的交易日，抓到的資料只存在自己的瀏覽器。
- **GitHub 上手動**：到 Actions → 更新借券雷達 → Run workflow，重新產生網站給所有人。

## 本機執行

```bash
python3 fetch_twse.py 10   # 抓最近 10 個交易日，寫出 data.json
python3 build.py           # 產生 site/index.html
```

資料僅供研究參考，不構成投資建議。
