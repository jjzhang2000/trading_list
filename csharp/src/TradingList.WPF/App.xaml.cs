using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using System.Windows;
using TradingList.Application.Services;
using TradingList.Core.Interfaces;
using TradingList.Infrastructure.Data;
using TradingList.Infrastructure.Repositories;
using TradingList.Infrastructure.Services;
using TradingList.WPF.ViewModels;

namespace TradingList.WPF;

/// <summary>
/// Application entry point
/// </summary>
public partial class App : Application
{
    private IHost? _host;

    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        _host = Host.CreateDefaultBuilder(e.Args)
            .ConfigureServices((context, services) =>
            {
                // Database
                services.AddTradingDbContext();
                
                // Repositories
                services.AddScoped<IStockDataRepository, StockDataRepository>();
                
                // Services
                services.AddScoped<ITechnicalIndicatorService, TechnicalIndicatorService>();
                services.AddScoped<IStockDataService, SinaFinanceService>();
                services.AddScoped<IPortfolioService, PortfolioService>();
                
                // Application Services
                services.AddScoped<StockFilterService>();
                services.AddScoped<DataSyncService>();
                services.AddScoped<CsvExportService>();
                
                // ViewModels
                services.AddScoped<MainViewModel>();
                
                // HttpClient
                services.AddHttpClient<SinaFinanceService>();
            })
            .Build();

        await _host.StartAsync();

        // Create and show main window
        var mainWindow = new MainWindow
        {
            DataContext = _host.Services.GetRequiredService<MainViewModel>()
        };
        mainWindow.Show();
    }

    protected override async void OnExit(ExitEventArgs e)
    {
        if (_host != null)
        {
            await _host.StopAsync();
            _host.Dispose();
        }
        
        base.OnExit(e);
    }
}
