using System.Net.Http.Json;
using System.Text.Json;
using System.Text.RegularExpressions;
using TradingList.Core.Interfaces;
using TradingList.Core.Models;

namespace TradingList.Infrastructure.Services;

/// <summary>
/// 新浪财经数据服务
/// </summary>
public class SinaFinanceService : IStockDataService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<SinaFinanceService> _logger;
    private const string BaseUrl = "http://quotes.sina.cn/cn/api/json_v2.php";
    private const string QfqUrl = "http://finance.sina.com.cn/realstock/company";

    public SinaFinanceService(HttpClient httpClient, ILogger<SinaFinanceService> logger)
    {
        _httpClient = httpClient;
        _logger = logger;
        _httpClient.DefaultRequestHeaders.Add("User-Agent", 
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");
    }

    public async Task<IEnumerable<(string Code, string Name)>> GetAllStocksAsync(
        CancellationToken cancellationToken = default)
    {
        var url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php" +
                  "/CN_MarketData.getHQNodeData?page=1&num=5000&node=sh_a";
        
        try
        {
            var response = await _httpClient.GetStringAsync(url, cancellationToken);
            
            // 新浪返回的是 JSON 格式但带有一些特殊字符
            response = response.Replace("var hq_str_sh000001=", "").Trim();
            
            var stocks = new List<(string, string)>();
            
            // 解析 JSON 数组
            var matches = Regex.Matches(response, @"code:""(\d{6})"".*?name:""([^""]+)""");
            foreach (Match match in matches)
            {
                var code = match.Groups[1].Value;
                var name = match.Groups[2].Value;
                
                // 只保留 60 开头的上证 A 股
                if (code.StartsWith("60"))
                {
                    stocks.Add((code, name));
                }
            }
            
            return stocks.OrderBy(s => s.Code);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "获取股票列表失败");
            return Enumerable.Empty<(string, string)>();
        }
    }

    public async Task<IEnumerable<StockPrice>> FetchStockDataAsync(
        string stockCode,
        DateTime startDate,
        DateTime endDate,
        CancellationToken cancellationToken = default)
    {
        var url = $"{BaseUrl}/CN_MarketDataService.getKLineData";
        var datalen = (endDate - startDate).Days + 100; // 预留一些数据
        
        var queryString = $"?symbol=sh{stockCode}&scale=240&datalen={datalen}";
        
        try
        {
            var response = await _httpClient.GetFromJsonAsync<List<SinaKLineData>>
                (url + queryString, cancellationToken);
            
            if (response == null)
            {
                _logger.LogWarning("获取股票 {StockCode} 数据返回空", stockCode);
                return Enumerable.Empty<StockPrice>();
            }
            
            // 获取复权因子
            var factors = await FetchAdjustFactorAsync(stockCode, cancellationToken);
            
            var prices = new List<StockPrice>();
            foreach (var item in response)
            {
                if (!DateTime.TryParse(item.Day, out var date))
                    continue;
                
                if (date < startDate || date > endDate)
                    continue;
                
                // 应用复权因子
                var factor = GetAdjustFactor(factors, item.Day);
                
                prices.Add(new StockPrice
                {
                    StockCode = stockCode,
                    Date = date,
                    Open = item.Open / factor,
                    High = item.High / factor,
                    Low = item.Low / factor,
                    Close = item.Close / factor,
                    Volume = (long)item.Volume
                });
            }
            
            return prices.OrderBy(p => p.Date);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "获取股票 {StockCode} 数据失败", stockCode);
            return Enumerable.Empty<StockPrice>();
        }
    }

    public async Task<Dictionary<string, decimal>> FetchAdjustFactorAsync(
        string stockCode,
        CancellationToken cancellationToken = default)
    {
        var url = $"{QfqUrl}/sh{stockCode}/qfq.js";
        
        try
        {
            var response = await _httpClient.GetStringAsync(url, cancellationToken);
            
            // 解析 JSON
            var startIdx = response.IndexOf('{');
            var endIdx = response.LastIndexOf('}');
            
            if (startIdx == -1 || endIdx == -1)
                return new Dictionary<string, decimal>();
            
            var json = response.Substring(startIdx, endIdx - startIdx + 1);
            var data = JsonSerializer.Deserialize<SinaAdjustFactor>(json);
            
            if (data?.Data == null)
                return new Dictionary<string, decimal>();
            
            return data.Data.ToDictionary(
                d => d.D,
                d => decimal.TryParse(d.F, out var f) ? f : 1.0m);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "获取股票 {StockCode} 复权因子失败", stockCode);
            return new Dictionary<string, decimal>();
        }
    }

    private static decimal GetAdjustFactor(Dictionary<string, decimal> factors, string date)
    {
        if (!factors.Any())
            return 1.0m;
        
        // 找到小于等于该日期的最大复权因子
        var factor = factors
            .Where(f => string.Compare(f.Key, date) <= 0)
            .OrderByDescending(f => f.Key)
            .FirstOrDefault();
        
        return factor.Value > 0 ? factor.Value : 1.0m;
    }

    // 新浪 K 线数据模型
    private class SinaKLineData
    {
        public string Day { get; set; } = string.Empty;
        public decimal Open { get; set; }
        public decimal High { get; set; }
        public decimal Low { get; set; }
        public decimal Close { get; set; }
        public decimal Volume { get; set; }
    }

    // 复权因子数据模型
    private class SinaAdjustFactor
    {
        public List<AdjustFactorItem> Data { get; set; } = new();
    }

    private class AdjustFactorItem
    {
        public string D { get; set; } = string.Empty;  // 日期
        public string F { get; set; } = string.Empty;  // 复权因子
    }
}
