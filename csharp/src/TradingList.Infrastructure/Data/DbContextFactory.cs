using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace TradingList.Infrastructure.Data;

/// <summary>
/// 数据库上下文工厂（用于设计时）
/// </summary>
public class TradingDbContextFactory : IDesignTimeDbContextFactory<TradingDbContext>
{
    public TradingDbContext CreateDbContext(string[] args)
    {
        var optionsBuilder = new DbContextOptionsBuilder<TradingDbContext>();
        
        // 数据库路径：%APPDATA%/TradingList/stock_data.db
        var appDataPath = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        var dbDirectory = Path.Combine(appDataPath, "TradingList");
        Directory.CreateDirectory(dbDirectory);
        
        var dbPath = Path.Combine(dbDirectory, "stock_data.db");
        optionsBuilder.UseSqlite($"Data Source={dbPath}");

        return new TradingDbContext(optionsBuilder.Options);
    }
}

/// <summary>
/// 数据库上下文配置扩展
/// </summary>
public static class DbContextExtensions
{
    public static IServiceCollection AddTradingDbContext(this IServiceCollection services)
    {
        services.AddDbContext<TradingDbContext>(options =>
        {
            var appDataPath = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            var dbDirectory = Path.Combine(appDataPath, "TradingList");
            Directory.CreateDirectory(dbDirectory);
            
            var dbPath = Path.Combine(dbDirectory, "stock_data.db");
            options.UseSqlite($"Data Source={dbPath}");
        });

        return services;
    }
}
