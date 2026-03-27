namespace TradingList.Core.Models;

/// <summary>
/// 股票每日价格数据
/// </summary>
public class StockPrice
{
    public int Id { get; set; }
    
    /// <summary>
    /// 股票代码（如：600000）
    /// </summary>
    public string StockCode { get; set; } = string.Empty;
    
    /// <summary>
    /// 日期
    /// </summary>
    public DateTime Date { get; set; }
    
    /// <summary>
    /// 前复权开盘价
    /// </summary>
    public decimal Open { get; set; }
    
    /// <summary>
    /// 前复权最高价
    /// </summary>
    public decimal High { get; set; }
    
    /// <summary>
    /// 前复权最低价
    /// </summary>
    public decimal Low { get; set; }
    
    /// <summary>
    /// 前复权收盘价
    /// </summary>
    public decimal Close { get; set; }
    
    /// <summary>
    /// 成交量
    /// </summary>
    public long Volume { get; set; }
}
