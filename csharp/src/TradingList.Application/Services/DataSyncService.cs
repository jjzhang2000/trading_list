using TradingList.Core.Interfaces;
using TradingList.Core.Models;

namespace TradingList.Application.Services;

/// <summary>
/// 数据同步服务
/// </summary>
public class DataSyncService
{
    private readonly IStockDataRepository _repository;
    private readonly IStockDataService _dataService;
    private readonly ILogger<DataSyncService> _logger;
    private const int RequestDelayMs = 300; // 0.3s 延迟

    public DataSyncService(
        IStockDataRepository repository,
        IStockDataService dataService,
        ILogger<DataSyncService> logger)
    {
        _repository = repository;
        _dataService = dataService;
        _logger = logger;
    }

    /// <summary>
    /// 初始化数据库
    /// </summary>
    public async Task InitializeDatabaseAsync(IProgress<string> progress)
    {
        progress.Report("正在初始化数据库...");
        await _repository.InitializeAsync();
        progress.Report("数据库初始化完成");
    }

    /// <summary>
    /// 同步所有股票数据
    /// </summary>
    public async Task SyncAllStocksAsync(
        int years = 5,
        IProgress<string> progress = null,
        CancellationToken cancellationToken = default)
    {
        progress?.Report("开始同步股票数据...");
        
        // 获取所有股票列表
        var stocks = await _dataService.GetAllStocksAsync(cancellationToken);
        progress?.Report($"发现 {stocks.Count()} 只股票");
        
        var endDate = DateTime.Today;
        var startDate = endDate.AddYears(-years);
        
        var count = 0;
        foreach (var (code, name) in stocks)
        {
            try
            {
                await SyncStockDataAsync(code, startDate, endDate, cancellationToken);
                await UpdateStockInfoAsync(code, name, cancellationToken);
                
                count++;
                progress?.Report($"已同步 {count}/{stocks.Count()}: {code} {name}");
                
                // 延迟避免触发 API 限制
                await Task.Delay(RequestDelayMs, cancellationToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "同步股票 {StockCode} 失败", code);
            }
        }
        
        progress?.Report($"同步完成，共 {count} 只股票");
    }

    /// <summary>
    /// 同步单只股票数据
    /// </summary>
    public async Task SyncStockDataAsync(
        string stockCode,
        DateTime startDate,
        DateTime endDate,
        CancellationToken cancellationToken = default)
    {
        var prices = await _dataService.FetchStockDataAsync(
            stockCode, startDate, endDate, cancellationToken);
        
        if (prices.Any())
        {
            await _repository.SaveStockPricesAsync(prices);
            _logger.LogDebug("保存股票 {StockCode} 的 {Count} 条记录", stockCode, prices.Count());
        }
    }

    /// <summary>
    /// 增量同步（只同步缺失的日期）
    /// </summary>
    public async Task IncrementalSyncAsync(
        IProgress<string> progress = null,
        CancellationToken cancellationToken = default)
    {
        progress?.Report("开始增量同步...");
        
        var allCodes = await _repository.GetAllStockCodesAsync();
        var endDate = DateTime.Today;
        
        var count = 0;
        foreach (var code in allCodes)
        {
            try
            {
                var info = await _repository.GetStockInfoAsync(code);
                if (info == null) continue;
                
                var startDate = info.EndDate.AddDays(1);
                if (startDate >= endDate) continue;
                
                await SyncStockDataAsync(code, startDate, endDate, cancellationToken);
                
                // 更新股票信息
                info.EndDate = endDate;
                info.TotalRecords = (await _repository.GetStockPriceInRangeAsync(
                    code, info.StartDate, info.EndDate)).Count();
                await _repository.UpdateStockInfoAsync(info);
                
                count++;
                progress?.Report($"增量同步: {code} ({startDate:yyyy-MM-dd} 至 {endDate:yyyy-MM-dd})");
                
                await Task.Delay(RequestDelayMs, cancellationToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "增量同步股票 {StockCode} 失败", code);
            }
        }
        
        progress?.Report($"增量同步完成，共 {count} 只股票");
    }

    /// <summary>
    /// 清空数据库
    /// </summary>
    public async Task ClearDatabaseAsync(IProgress<string> progress)
    {
        progress?.Report("正在清空数据库...");
        await _repository.ClearDatabaseAsync();
        progress?.Report("数据库已清空");
    }

    /// <summary>
    /// 更新股票信息
    /// </summary>
    private async Task UpdateStockInfoAsync(string stockCode, string stockName, CancellationToken cancellationToken)
    {
        var prices = await _repository.GetStockPriceBeforeDateAsync(
            stockCode, DateTime.MaxValue, int.MaxValue);
        
        if (prices.Any())
        {
            var info = new StockInfo
            {
                StockCode = stockCode,
                StockName = stockName,
                TotalRecords = prices.Count(),
                StartDate = prices.Min(p => p.Date),
                EndDate = prices.Max(p => p.Date)
            };
            
            await _repository.UpdateStockInfoAsync(info);
        }
    }
}
