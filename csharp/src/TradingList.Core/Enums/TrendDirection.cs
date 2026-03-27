namespace TradingList.Core.Enums;

/// <summary>
/// 趋势方向
/// </summary>
public enum TrendDirection
{
    /// <summary>
    /// 震荡
    /// </summary>
    Neutral = 0,
    
    /// <summary>
    /// 多头
    /// </summary>
    Bullish = 1,
    
    /// <summary>
    /// 空头
    /// </summary>
    Bearish = -1
}
