namespace TradingList.Core.Models;

/// <summary>
/// 股票基本信息
/// </summary>
public class StockInfo
{
    /// <summary>
    /// 股票代码（如：600000）
    /// </summary>
    public string StockCode { get; set; } = string.Empty;
    
    /// <summary>
    /// 股票名称
    /// </summary>
    public string StockName { get; set; } = string.Empty;
    
    /// <summary>
    /// 总记录数
    /// </summary>
    public int TotalRecords { get; set; }
    
    /// <summary>
    /// 数据开始日期
    /// </summary>
    public DateTime StartDate { get; set; }
    
    /// <summary>
    /// 数据结束日期
    /// </summary>
    public DateTime EndDate { get; set; }
}
