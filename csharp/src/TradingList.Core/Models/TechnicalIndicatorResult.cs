using TradingList.Core.Enums;

namespace TradingList.Core.Models;

/// <summary>
/// 技术指标结果基类
/// </summary>
public abstract class TechnicalIndicatorResult
{
    public string StockCode { get; set; } = string.Empty;
    public DateTime Date { get; set; }
    public decimal Close { get; set; }
    public TrendDirection TrendDirection { get; set; }
}

/// <summary>
/// SuperTrend 指标结果
/// </summary>
public class SuperTrendResult : TechnicalIndicatorResult
{
    public decimal SuperTrendValue { get; set; }
    
    /// <summary>
    /// 收盘价高于 SuperTrend 线的幅度（%）
    /// </summary>
    public decimal AbovePercentage => Close > 0 && SuperTrendValue > 0
        ? (Close - SuperTrendValue) / SuperTrendValue * 100
        : 0;
    
    /// <summary>
    /// 标准化评分（0-10）
    /// </summary>
    public decimal Score => Math.Min(AbovePercentage / 10, 10);
}

/// <summary>
/// Vegas 通道指标结果
/// </summary>
public class VegasChannelResult : TechnicalIndicatorResult
{
    public decimal Ema12 { get; set; }
    public decimal Ema26 { get; set; }
    public decimal Ema144 { get; set; }
    public decimal Ema169 { get; set; }
    public decimal Ema576 { get; set; }
    public decimal Ema676 { get; set; }
    
    /// <summary>
    /// 收盘价高于 EMA144 的幅度（%）
    /// </summary>
    public decimal AboveEma144Percentage => Close > 0 && Ema144 > 0
        ? (Close - Ema144) / Ema144 * 100
        : 0;
    
    /// <summary>
    /// 标准化评分（0-10）
    /// </summary>
    public decimal Score => Math.Min(AboveEma144Percentage / 20, 10);
}

/// <summary>
/// 布林带指标结果
/// </summary>
public class BollingerBandResult : TechnicalIndicatorResult
{
    public decimal MiddleBand { get; set; }
    public decimal UpperBand { get; set; }
    public decimal LowerBand { get; set; }
    
    /// <summary>
    /// 开口率（%）
    /// </summary>
    public decimal Bandwidth => MiddleBand > 0
        ? (UpperBand - LowerBand) / MiddleBand * 100
        : 0;
    
    /// <summary>
    /// 是否高于中轨
    /// </summary>
    public bool IsAboveMiddle => Close > MiddleBand;
    
    /// <summary>
    /// 标准化评分（0-10）
    /// </summary>
    public decimal Score => Math.Min(Bandwidth / 10, 10);
}

/// <summary>
/// OCC（Open/Close Cross）指标结果
/// </summary>
public class OccResult : TechnicalIndicatorResult
{
    public decimal OccOpen { get; set; }
    public decimal OccClose { get; set; }
    
    /// <summary>
    /// OCC Close 高于 OCC Open 的幅度（%）
    /// </summary>
    public decimal AbovePercentage => OccOpen > 0
        ? (OccClose - OccOpen) / OccOpen * 100
        : 0;
    
    /// <summary>
    /// 标准化评分（0-10）
    /// </summary>
    public decimal Score => Math.Min(AbovePercentage / 5 * 10, 10);
}

/// <summary>
/// VP Slope 指标结果
/// </summary>
public class VpSlopeResult : TechnicalIndicatorResult
{
    public decimal SlopeLong { get; set; }
    public decimal SlopeShort { get; set; }
    
    /// <summary>
    /// 标准化评分（0-10）
    /// </summary>
    public decimal Score => SlopeLong > 0
        ? Math.Min(SlopeLong * 100, 10)
        : 0;
}
