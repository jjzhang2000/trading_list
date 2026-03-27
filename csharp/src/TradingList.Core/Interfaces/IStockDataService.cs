using TradingList.Core.Models;

namespace TradingList.Core.Interfaces;

/// <summary>
/// 股票数据服务接口（外部数据源）
/// </summary>
public interface IStockDataService
{
    /// <summary>
    /// 获取所有股票列表
    /// </summary>
    Task<IEnumerable<(string Code, string Name)>> GetAllStocksAsync(
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// 获取股票历史数据
    /// </summary>
    Task<IEnumerable<StockPrice>> FetchStockDataAsync(
        string stockCode,
        DateTime startDate,
        DateTime endDate,
        CancellationToken cancellationToken = default);
    
    /// <summary>
    /// 获取前复权因子
    /// </summary>
    Task<Dictionary<string, decimal>> FetchAdjustFactorAsync(
        string stockCode,
        CancellationToken cancellationToken = default);
}
