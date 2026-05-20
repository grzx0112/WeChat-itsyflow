# 数据源清单

## 1. FDA openFDA API

### Drug Event（不良事件）
- 端点：`https://api.fda.gov/drug/event.json`
- 搜索参数：`search=patient.drug.medicinalproduct:"{keyword}"`
- 限制：无 key 每分钟 240 请求，有 key 1200 请求
- 返回：JSON

### Drugs@FDA（药品审批）
- 端点：`https://api.fda.gov/drug/drugsfda.json`
- 搜索参数：`search=products.brand_name:"{keyword}"+openfda.application_type:"NDA"`
- 限制：同上
- 返回：JSON

### Drug Label（药品标签）
- 端点：`https://api.fda.gov/drug/label.json`
- 搜索参数：`search=openfda.brand_name:"{keyword}"`
- 限制：同上
- 返回：JSON

## 2. PubMed E-utilities

### esearch（搜索）
- 端点：`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi`
- 参数：`db=pubmed, term={keyword}, retmax=50, datetype=pdat, mindate/maxdate`
- 限制：3 请求/秒（无 key），10 请求/秒（有 API key）

### efetch（获取详情）
- 端点：`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi`
- 参数：`db=pubmed, id={uid_list}, rettype=abstract, retmode=xml`
- 返回：XML

## 3. RSS 新闻源

| 源 | RSS URL | 说明 |
|---|---------|------|
| BioPharma Dive | `https://www.biopharmadive.com/feeds/news/` | 生物制药行业新闻 |
| Fierce Pharma | `https://www.fiercepharma.com/rss/xml` | 制药行业新闻 |
| STAT News | `https://www.statnews.com/feed/` | 医药科学新闻 |
| Endpoints News | `https://endpts.com/feed/` | 生物技术新闻 |
| Drug Discovery Online | `https://www.drugdiscoveryonline.com/rss` | 药物发现 |

### 配额说明
- RSS 通常无频率限制，但建议间隔 ≥ 5 分钟
- feedparser 解析，关键词在标题/摘要中匹配
