namespace TradingList.Core.Models;

/// <summary>
/// 筛选选项
/// </summary>
public class FilterOptions
{
    /// <summary>
    /// 筛选日期
    /// </summary>
    public DateTime Date { get; set; } = DateTime.Today;
    
    /// <summary>
    /// 是否启用 SuperTrend 筛选
    /// </summary>
    public bool EnableSuperTrend { get; set; } = true;
    
    /// <summary>
    /// 是否启用 Vegas 通道筛选
    /// </summary>
    public bool EnableVegas { get; set; } = true;
    
    /// <summary>
    /// 是否启用布林带筛选
    /// </summary>
    public bool EnableBollingerBand { get; set; } = true;
    
    /// <summary>
    /// 是否启用 OCC 筛选
    /// </summary>
    public bool EnableOcc { get; set; } = true;
    
    /// <summary>
    /// 是否启用 VP Slope 筛选
    /// </summary>
    public bool EnableVpSlope { get; set; } = true;
    
    /// <summary>
    /// 布林带开口率阈值（%）
    /// </summary>
    public decimal BollingerBandwidthThreshold { get; set; } = 10.0m;
    
    /// <summary>
    /// SuperTrend ATR 周期
    /// </summary>
    public int SuperTrendPeriod { get; set; } = 10;
    
    /// <summary>
    /// SuperTrend ATR 乘数
    /// </summary>
    public decimal SuperTrendMultiplier { get; set; } = 3.0m;
    
    /// <summary>
    /// OCC 周期
    /// </summary>
    public int OccPeriod { get; set; } = 8;
    
    /// <summary>
    /// OCC 移动平均类型
    /// </summary>
    public Enums.MaType OccMaType { get; set; } = Enums.MaType.TMA;
    
    /// <summary>
    /// VP Slope 长期周期
    /// </summary>
    public int VpSlopeLongPeriod { get; set; } = 100;
    
    /// <summary>
    /// VP Slope 短期周期
    /// </summary>
    public int VpSlopeShortPeriod { get; set; } = 10;
}
