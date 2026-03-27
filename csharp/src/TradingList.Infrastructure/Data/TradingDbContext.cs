using Microsoft.EntityFrameworkCore;
using TradingList.Core.Models;

namespace TradingList.Infrastructure.Data;

/// <summary>
/// 交易数据库上下文
/// </summary>
public class TradingDbContext : DbContext
{
    public TradingDbContext(DbContextOptions<TradingDbContext> options) : base(options)
    {
    }

    /// <summary>
    /// 股票日线数据
    /// </summary>
    public DbSet<StockPrice> StockPrices { get; set; } = null!;
    
    /// <summary>
    /// 股票信息
    /// </summary>
    public DbSet<StockInfo> StockInfos { get; set; } = null!;

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        base.OnModelCreating(modelBuilder);

        // StockPrice 配置
        modelBuilder.Entity<StockPrice>(entity =>
        {
            entity.ToTable("stock_daily");
            entity.HasKey(e => e.Id);
            entity.Property(e => e.Id).ValueGeneratedOnAdd();
            entity.Property(e => e.StockCode).HasMaxLength(10).IsRequired();
            entity.Property(e => e.Date).IsRequired();
            entity.Property(e => e.Open).HasPrecision(18, 4);
            entity.Property(e => e.High).HasPrecision(18, 4);
            entity.Property(e => e.Low).HasPrecision(18, 4);
            entity.Property(e => e.Close).HasPrecision(18, 4);
            entity.Property(e => e.Volume);
            
            // 唯一索引：股票代码 + 日期
            entity.HasIndex(e => new { e.StockCode, e.Date }).IsUnique();
        });

        // StockInfo 配置
        modelBuilder.Entity<StockInfo>(entity =>
        {
            entity.ToTable("stock_info");
            entity.HasKey(e => e.StockCode);
            entity.Property(e => e.StockCode).HasMaxLength(10);
            entity.Property(e => e.StockName).HasMaxLength(100);
            entity.Property(e => e.TotalRecords);
            entity.Property(e => e.StartDate);
            entity.Property(e => e.EndDate);
        });
    }
}
