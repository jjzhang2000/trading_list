namespace TradingList.Core.Enums;

/// <summary>
/// 移动平均类型
/// </summary>
public enum MaType
{
    /// <summary>
    /// 简单移动平均
    /// </summary>
    SMA,
    
    /// <summary>
    /// 指数移动平均
    /// </summary>
    EMA,
    
    /// <summary>
    /// 双指数移动平均
    /// </summary>
    DEMA,
    
    /// <summary>
    /// 三重指数移动平均
    /// </summary>
    TEMA,
    
    /// <summary>
    /// 加权移动平均
    /// </summary>
    WMA,
    
    /// <summary>
    /// 成交量加权移动平均
    /// </summary>
    VWMA,
    
    /// <summary>
    /// 平滑移动平均
    /// </summary>
    SSMA,
    
    /// <summary>
    /// 三角移动平均
    /// </summary>
    TMA
}
