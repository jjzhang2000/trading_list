using TradingList.Core.Models;

namespace TradingList.Core.Interfaces;

/// <summary>
/// 股票数据仓库接口
/// </summary>
public interface IStockDataRepository
{
    /// <summary>
    /// 初始化数据库
    /// </summary>
    Task InitializeAsync();
    
    /// <summary>
    /// 获取所有股票代码
    /// </summary>
    Task<IEnumerable<string>> GetAllStockCodesAsync();
    
    /// <summary>
    /// 获取股票名称
    /// </summary>
    Task<string?> GetStockNameAsync(string stockCode);
    
    /// <summary>
    /// 获取指定日期之前的股票数据
    /// </summary>
    Task<IEnumerable<StockPrice>> GetStockPriceBeforeDateAsync(
        string stockCode, 
        DateTime endDate, 
        int limit);
    
    /// <summary>
    /// 获取指定日期范围内的股票数据
    /// </summary>
    Task<IEnumerable<StockPrice>> GetStockPriceInRangeAsync(
        string stockCode,
        DateTime startDate,
        DateTime endDate);
    
    /// <summary>
    /// 获取指定日期的所有股票数据
    /// </summary>
    Task<IEnumerable<StockPrice>> GetAllStocksPriceOnDateAsync(DateTime date);
    
    /// <summary>
    /// 保存股票数据
    /// </summary>
    Task SaveStockPricesAsync(IEnumerable<StockPrice> prices);
    
    /// <summary>
    /// 更新股票信息
    /// </summary>
    Task UpdateStockInfoAsync(StockInfo info);
    
    /// <summary>
    /// 获取股票信息
    /// </summary>
    Task<StockInfo?> GetStockInfoAsync(string stockCode);
    
    /// <summary>
    /// 清空数据库
    /// </summary>
    Task ClearDatabaseAsync();
}
