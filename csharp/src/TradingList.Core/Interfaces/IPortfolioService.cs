namespace TradingList.Core.Interfaces;

/// <summary>
/// 持仓服务接口
/// </summary>
public interface IPortfolioService
{
    /// <summary>
    /// 获取持仓股票代码列表
    /// </summary>
    Task<IEnumerable<string>> GetPortfolioStocksAsync();
    
    /// <summary>
    /// 添加持仓股票
    /// </summary>
    Task AddPortfolioStockAsync(string stockCode);
    
    /// <summary>
    /// 移除持仓股票
    /// </summary>
    Task RemovePortfolioStockAsync(string stockCode);
    
    /// <summary>
    /// 检查是否为持仓股票
    /// </summary>
    Task<bool> IsPortfolioStockAsync(string stockCode);
}
