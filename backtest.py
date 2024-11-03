import ta
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from binance.client import Client 
from sqlalchemy import create_engine, inspect
import os
from datetime import datetime
from tabulate import tabulate

class DataSQL():
    db = 'live_crypto.db'
    
    def __init__(self, symbol, interval, start, end) -> None:
        self.symbol = symbol
        self.interval = interval
        self.start = start
        self.end = end
        self.client = Client()
        self.df_sql = None
        self.db = 'live_crypto.db'
        self.data()  # Fetch historical data
        self.database()  # Create database connection
        self.save_to_sql()  # Save data to SQL
        pd.read_sql(self.table_name, self.engine)  # Read SQL table
        
    def data(self):
        # Define time intervals
        intervals = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15,
            '30m': 30, '1h': 60, '2h': 120,
            '4h': 240, '1d': 1440, '2d': 2880,
            '1w': 10080
        }
        
        # Fetch and format historical data
        self.df = pd.DataFrame(self.client.get_historical_klines(self.symbol, self.interval, self.start, self.end))
        self.df = self.df[[0, 1, 2, 3, 4, 5]]
        self.df.columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
        self.df.Date = pd.to_datetime(self.df.Date, unit='ms')
        self.df.set_index('Date', inplace=True)
        self.df[["Open", "High", "Low", "Close", "Volume"]] = self.df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
        self.df['pct_change24h'] = self.df['Close'].pct_change(periods=(24 * 60) // intervals[self.interval]) * 100

        # Calculate indicators
        self.df['ma_7'] = self.df.Close.rolling(7).mean()  # 7-period moving average
        self.df['ma_21'] = self.df.Close.rolling(21).mean()  # 21-period moving average
        self.df['vol'] = self.df.Close.rolling(21).std()  # 21-period volatility
        self.df['upper_bb'] = self.df.ma_21 + (2 * self.df.vol)  # Upper Bollinger Band
        self.df['lower_bb'] = self.df.ma_21 - (2 * self.df.vol)  # Lower Bollinger Band
        self.df['rsi'] = ta.momentum.rsi(self.df.Close, window=14)  # RSI calculation
        self.df['price'] = self.df.Open.shift(-1)  # Next period's opening price
        self.df.dropna(inplace=True)  # Remove missing values

        if self.df.empty:
            raise ValueError('DataFrame is empty')  # Raise error if DataFrame is empty
        
        return self.df
    
    def database(self):
        self.engine = create_engine('sqlite:///' + self.db)  # Create SQL engine
        return self.engine

    def save_to_sql(self):
        start_index = str(self.df.index[1])[:10].replace(" ", "-").replace(":", "-")
        self.table_name = str(self.interval + self.symbol + start_index)  # Table name based on parameters
        
        try:
            if not os.path.exists(self.db):  # Check if database exists
                print(f'DB NOT Exists .. Creating New DB: {self.table_name}')
                self.df_sql = self.df.to_sql(self.table_name, self.engine)  # Save DataFrame to SQL
                self.engine.dispose()  # Close engine connection
                return self.df_sql 

            elif os.path.exists(self.db):  # If database exists
                inspector = inspect(self.engine)
                if self.table_name in inspector.get_table_names():  # Check if table exists
                    self.df_sql = pd.read_sql(self.table_name, self.engine)
                    self.max_date_sql = self.df_sql['Date'].iloc[-1].strftime('%Y-%m-%d %H:%M:%S')
                    self.NotUpdatedRows = self.df[self.df.index > self.max_date_sql] 
                    self.df[self.df.index > self.max_date_sql].to_sql(self.table_name, self.engine, if_exists='append')  # Append new rows
                    print(f'DB and Table already exists .. Updating: {self.table_name} by: {len(self.NotUpdatedRows)} rows ')
                    self.engine.dispose()  # Close engine connection
                    return self.df_sql
                
                elif self.table_name not in inspector.get_table_names():  # Create new table
                    print(f'DB already exists .. Creating new Table for {self.table_name}')
                    self.df_sql = self.df.to_sql(self.table_name, self.engine)  # Save DataFrame to new table
                    self.engine.dispose()  # Close engine connection
                    return self.df_sql      

        except:
            self.engine.dispose()  # Close engine connection on error
            raise Warning('DF to SQL has an issue')  # Raise warning if an error occurs


class SqlReader(DataSQL):
    def __init__(self) -> None:
        self.db = DataSQL.db  # Inherit database name
        self.engine = create_engine(f'sqlite:///{self.db}')  # Create SQL engine
        self.tables = [] 
        self.tables = inspect(self.engine).get_table_names()  # Get table names
        
    def get_tables(self):
        return self.tables  # Return available table names

    def df_sql_reader(self, table_index=None):
        """Fetches data from a selected table by index and returns it as a DataFrame."""
        try:
            self.tables
            
            if not self.tables:
                print("No tables available in the database.")
                return None
            
            # Display list of tables
            print("Available tables:")
            for idx, self.table_name in enumerate(self.tables, 1):
                print(f"{idx}: {self.table_name}")

            # Prompt user to choose a table if no index is provided
            if table_index is None:
                table_index = int(input("Enter the number of the table to print: "))

            # Validate selected index
            if table_index < 1 or table_index > len(self.tables):
                print(f"Invalid selection. Please enter a number between 1 and {len(self.tables)}.")
                return None

            # Read the selected table into a DataFrame
            self.table_name = self.tables[table_index - 1]
            self.df_sql = pd.read_sql(self.table_name, self.engine)
            return self.df_sql

        except Exception as e:
            print(f"Error reading from database: {e}")
            return None
        finally:
            self.engine.dispose()  # Ensure the database connection is closed

    def df_sql_reader2(self, name_table):
        try:
            if len(self.tables) > 0:
                self.name_table = name_table
                self.df_sql = pd.read_sql(self.name_table, self.engine)
                return self.df_sql

        except:
            raise Warning('No Tables Found')  # Raise warning if no tables are found


class Backtest():
    _db = None  # Class-level variable for database name

    @classmethod
    def set_db(cls, db):
        """Class method to set the database name once."""
        cls._db = db

    def __init__(self, cash, fees, db=None, **kwargs):
        # SqlReaderself = SqlReader()  # Initialize SqlReader instance
        # SqlReaderself.get_tables()
        # self.sql_db = sql_db
        # if self.sql_db == None:
        #     self.sql_db = SqlReaderself.df_sql_reader2(name_tabel='5mBTCUSDT2024-05-07') #input('Enter Tabel Name: ')
        self.db = Backtest._db
        self.engine = create_engine(f'sqlite:///live_crypto.db')
        self.df = pd.read_sql_table(self.db, self.engine)
        self.cash = cash
        self.fees = fees
        self.tp = kwargs.get('tp', 0)
        self.sl = kwargs.get('sl', 0)
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.client = Client()
        #self.df = None
        self.get_data()
        if self.df.empty:
            print('Dataframe is Empty')
        else: 
            self.generate_signals()
            self.find_trades()
            self.calc_profit()
            self.cals()
            self.output
            
    def get_data(self):
        #self.df = self.sql_db
        # Convert to datetime if necessary
        self.df['Date'] = pd.to_datetime(self.df['Date'])
        self.df.set_index('Date', inplace=True)

        return self.df

        
    def generate_signals(self):
#         conditions = [(self.df.rsi < 30) & (self.df.Close < self.df.lower_bb), \
#                       (self.df.rsi > 70) & (self.df.Close > self.df.upper_bb)]
        
        conditions = [(self.df.rsi < self.rsi_buy) & (self.df.pct_change24h < self.pct_buy ), \
                      (self.df.rsi > self.rsi_sell) & (self.df.pct_change24h > self.pct_sell)]
    
        choices = ['Buy', 'Sell']
        self.df['signal'] = np.select(conditions, choices)
        self.df.signal = self.df.signal.shift()
        self.df.dropna (inplace=True)
        return self.df

    
    def find_trades(self):
        position = False
        buydates, selldates = [], []
        buy_price = 0
        for index, row in self.df.iterrows():
            if not position and row['signal'] == 'Buy':
                position = True
                buy_price = row['Open']
                buydates.append(index)
            if self.tp != 0 or self.sl != 0:    
                if position and (row['signal'] == 'Sell') and \
                ( (row['Close'] > buy_price * (1+ self.tp)) or (row['Close'] > buy_price * (1- self.sl))  ):
                    position = False
                    selldates.append(index)
                    buy_price = 0
            if self.tp == 0 and self.sl == 0:        
                if position and (row['signal'] == 'Sell'):
                        position = False
                        selldates.append(index)
                        buy_price = 0
        self.buy_arr = self.df.loc[buydates].Open 
        self.sell_arr = self.df.loc[selldates].Open

    
    def calc_profit(self):
    # Check if both buy_arr and sell_arr are non-empty
        if not self.buy_arr.empty and not self.sell_arr.empty:
            # Ensure last buy date is earlier than last sell date
            if self.buy_arr.index[-1] > self.sell_arr.index[-1]:
                self.buy_arr = self.buy_arr[:-1]

            # Adjusted profit calculation with fees
            adjusted_buy = self.buy_arr.values * (1 + self.fees)
            adjusted_sell = self.sell_arr.values * (1 - self.fees)
            self.net_profit = (adjusted_sell - adjusted_buy) / adjusted_buy  # Return profit as a percentage
        else:
            # If no trades, return zero profit
            self.net_profit = pd.Series([0.0])  # Use zero profit if no trades executed
        return self.net_profit

    def plot_chart(self):
        plt.figure(figsize=(12, 6))

        # Plot closing prices and trade signals
        plt.plot(self.df['Close'], label='Close Price', color='black', alpha=0.6)
        plt.scatter(self.buy_arr.index, self.buy_arr.values, marker='^', c='g', s=130, label='Buy Signal')
        plt.scatter(self.sell_arr.index, self.sell_arr.values, marker='v', c='r', s=130, label='Sell Signal')

        # Create a Series for returns aligned with the DataFrame index
        returns = pd.Series(0, index=self.df.index)  # Initialize with zeros for all indices
        returns.loc[self.buy_arr.index] = self.net_profit  # Fill in the net profits where trades occurred

        # Calculate cumulative returns
        cumulative_returns = (1 + returns).cumprod()

        # Plot cumulative returns as a performance line
        plt.plot(cumulative_returns.index, cumulative_returns.values * self.cash, label='Equity Curve', color='blue')

        # Mean of cumulative returns (displayed as a horizontal line)
        mean_return = cumulative_returns.mean() * self.cash
        plt.axhline(y=mean_return, color='orange', linestyle='--', label=f'Mean Return (${mean_return:.2f})')

        # Add final equity and number of trades as annotations
        final_equity = cumulative_returns.iloc[-1] * self.cash
        num_trades = len(self.buy_arr)
        win_rate = (self.buy_arr[self.buy_arr.index].values - self.sell_arr[self.sell_arr.index].values > 0).mean() * 100 if num_trades > 0 else np.nan
        max_drawdown = cumulative_returns.min() * self.cash
        
        plt.text(0.02, 0.95, f'Final Equity: ${final_equity:.2f}', transform=plt.gca().transAxes, fontsize=10, color='green')
        plt.text(0.02, 0.90, f'Number of Trades: {num_trades}', transform=plt.gca().transAxes, fontsize=10, color='purple')
        plt.text(0.02, 0.85, f'Win Rate: {win_rate:.2f}%', transform=plt.gca().transAxes, fontsize=10, color='blue')
        plt.text(0.02, 0.80, f'Max Drawdown: {max_drawdown:.2f}', transform=plt.gca().transAxes, fontsize=10, color='orange')

        # Labels, title, and legend
        plt.xlabel('Date')
        plt.ylabel('Price / Equity')
        plt.title('Trading Strategy Performance with Cumulative Return')
   

    def cals(self):
        # Ensure profits are a Pandas Series
        returns = pd.Series(self.net_profit)
        # Cumulative return as a Pandas Series
        cum_returns = (1 + returns).cumprod() - 1

        # Core metrics
        total_return = cum_returns.iloc[-1] * 100  # Percentage return
        days_held = (self.df.index[-1] - self.df.index[0]).days
        years_held = days_held / 365.25
        annualized_return = ((1 + total_return / 100) **
                            (1 / years_held) - 1) * 100 if years_held > 0 else np.nan

        # Annualized volatility (using the square root of trading periods)
        volatility = returns.std() * (365.25 ** 0.5) * 100 if len(returns) > 1 else np.nan

        # Sharpe Ratio
        risk_free_rate = 0.01  # Adjust as necessary
        sharpe_ratio = (annualized_return - risk_free_rate * 100) / \
            volatility if volatility and volatility != 0 else np.nan

        # Drawdown calculations
        drawdown = cum_returns - cum_returns.cummax()
        max_drawdown = drawdown.min() * 100
        avg_drawdown = drawdown[drawdown < 0].mean(
        ) * 100 if not drawdown[drawdown < 0].empty else np.nan

        # Calculate durations
        start_date = self.df.index[0]
        end_date = self.df.index[-1]
        duration = end_date - start_date
        exposure_time = len(self.df[self.df['signal'] != '']) / \
            len(self.df) * 100 if len(self.df) > 0 else 0

        # Trade stats: only calculate if trades exist, otherwise set specific metrics to NaN
        try:
            num_trades = len(self.buy_arr)
            if num_trades > 0 and (len(self.sell_arr) > 0):
                win_trades = (self.sell_arr.values - self.buy_arr.values) > 0
                win_rate = (win_trades.sum() / num_trades) * 100
                best_trade = returns.max() * 100
                worst_trade = returns.min() * 100
                avg_trade = returns.mean() * 100
                profit_factor = returns[returns > 0].sum(
                ) / -returns[returns < 0].sum() if returns[returns < 0].sum() != 0 else np.nan
            else:
                win_rate = np.nan
                best_trade = np.nan
                worst_trade = np.nan
                avg_trade = np.nan
                profit_factor = np.nan
        except Exception:
            num_trades = 0
            win_rate = np.nan
            best_trade = np.nan
            worst_trade = np.nan
            avg_trade = np.nan
            profit_factor = np.nan

        # Equity and cash calculations
        equity_final = self.cash * (1 + cum_returns.iloc[-1])
        equity_peak = self.cash * (1 + cum_returns).max()

        # Create Series with all metrics
        self.output = pd.Series({
            'Start': start_date,
            'End': end_date,
            'Duration': duration,
            'Exposure Time [%]': min(exposure_time, 100),
            'Equity Final [$]': equity_final,
            'Equity Peak [$]': equity_peak,
            'Return [%]': total_return,
            'Buy & Hold Return [%]': ((self.df['Close'].iloc[-1] / self.df['Close'].iloc[0]) - 1) * 100,
            'Return (Ann.) [%]': annualized_return,
            'Volatility (Ann.) [%]': volatility,
            'Sharpe Ratio': sharpe_ratio,
            'Max. Drawdown [%]': max_drawdown,
            'Avg. Drawdown [%]': avg_drawdown,
            'Max. Drawdown Duration': drawdown.idxmin() - drawdown.idxmax() if max_drawdown < 0 else pd.Timedelta(0),
            'Avg. Drawdown Duration': pd.to_timedelta(drawdown[drawdown < 0].index.to_series().diff().mean()).round("1min") if not drawdown[drawdown < 0].empty else pd.Timedelta(0),
            '# Trades': num_trades,
            'Win Rate [%]': win_rate,
            'Best Trade [%]': best_trade,
            'Worst Trade [%]': worst_trade,
            'Avg. Trade [%]': avg_trade,
            'Profit Factor': profit_factor,
            'Final Cash': equity_final
        })

        return self.output


# if __name__ == "__main__":
#     # Initialize the DataSQL object
#     # bt = DataSQL('BTCUSDT', '15m', '365 days ago UTC', 'now')
#     bt = DataSQL('BTCUSDT', '1h', '2020-05-01', '2024-11-01')
    
#     reader = SqlReader()
#     print(reader.get_tables())
#     Backtest.set_db(input('Please write name of table: '))

#     # Define parameter ranges
#     pct_buy = np.round(np.arange(-4, 5, 0.3), 1)    # Pct buy thresholds
#     pct_sell = np.round(np.arange(0, 5, 0.3), 1)   # Pct sell thresholds
#     rsi_buy = np.arange(15, 30, 2)                  # RSI Buy thresholds
#     rsi_sell = np.arange(75, 95, 2)                 # RSI Sell thresholds

#     # Create DataFrames for each parameter
#     df_pct_buy = pd.DataFrame(pct_buy, columns=['pct_buy'])
#     df_pct_sell = pd.DataFrame(pct_sell, columns=['pct_sell'])
#     df_rsi_buy = pd.DataFrame(rsi_buy, columns=['rsi_buy'])
#     df_rsi_sell = pd.DataFrame(rsi_sell, columns=['rsi_sell'])

#     # Perform cross join to create all combinations
#     df_cross = df_pct_buy.merge(df_pct_sell, how='cross').merge(df_rsi_buy, how='cross').merge(df_rsi_sell, how='cross')

#     # Specify the CSV file path
#     csv_file_path = 'live_results.csv'

#     # Initialize an empty DataFrame to collect outputs
#     output_df = pd.DataFrame()

#     # Initialize variable to store the last final equity
#     last_final_equity = None

#     # Check if CSV exists and read last row if it does
#     if os.path.exists(csv_file_path):
#         df_existing = pd.read_csv(csv_file_path)
#         if not df_existing.empty:  # Check if df_existing is not empty
#             # Remove the last three rows
#             df_existing = df_existing[:-3]
#             df_existing.to_csv(csv_file_path, index=False)  # Update the CSV

#             # Get the last parameters used from the existing CSV
#             last_row = df_existing.iloc[-1]  # Safe to access the last row now
#             last_pct_buy = last_row['pct_buy']
#             last_pct_sell = last_row['pct_sell']
#             last_rsi_buy = last_row['rsi_buy']
#             last_rsi_sell = last_row['rsi_sell']

#             # Filter df_cross to only include combinations after the last recorded row
#             df_cross = df_cross[(df_cross['pct_buy'] > last_pct_buy) | 
#                                 ((df_cross['pct_buy'] == last_pct_buy) & (df_cross['pct_sell'] > last_pct_sell)) |
#                                 ((df_cross['pct_buy'] == last_pct_buy) & (df_cross['pct_sell'] == last_pct_sell) & (df_cross['rsi_buy'] > last_rsi_buy)) |
#                                 ((df_cross['pct_buy'] == last_pct_buy) & (df_cross['pct_sell'] == last_sell) & (df_cross['rsi_buy'] == last_rsi_buy) & (df_cross['rsi_sell'] > last_rsi_sell))]
#         else:
#             print("The existing CSV file is empty. Proceeding with all parameter combinations.")

#     # Loop over each parameter combination
#     for _, row in df_cross.iterrows():
#         # Run the Backtest with each parameter combination
#         backtest = Backtest(
#             cash=1000,  # Initial cash amount used for backtest
#             fees=0.001,
#             rsi_buy=row['rsi_buy'],
#             rsi_sell=row['rsi_sell'],
#             pct_buy=row['pct_buy'],
#             pct_sell=row['pct_sell'],
#             tp=0,
#             sl=0
#         )

#         # Assume `backtest.output` returns a dictionary-like structure for easy conversion
#         output_series = pd.Series(backtest.output)

#         # Add the current parameters to the output for reference
#         output_series = pd.concat([row, output_series])

#         # Get the final equity from the output
#         current_final_equity = backtest.output.get('Final Cash')

#         # Check if the final equity is different from the initial cash and has changed compared to last recorded equity
#         if current_final_equity != 1000 and (last_final_equity is None or current_final_equity != last_final_equity):
#             # Append the output to the DataFrame
#             output_df = pd.concat([output_df, output_series.to_frame().T], ignore_index=True)

#             # Update the last final equity
#             last_final_equity = current_final_equity
            
#             # Append the results to the CSV file
#             output_df.to_csv(csv_file_path, mode='a', header=not pd.io.common.file_exists(csv_file_path), index=False)

#             dt = datetime.now()
#             if dt.minute % 2 == 0 and (18 <= dt.second <= 20):
#                 print("\033c")
#                 df = pd.read_csv(csv_file_path)
#                 sorted_df = df.sort_values(by=['Final Cash', 'Max. Drawdown [%]'], 
#                                             ascending=[False, True])

#                 # Filter to only keep rows where Max. Drawdown [%] is greater than -50%
#                 filtered_df = sorted_df[sorted_df['Max. Drawdown [%]'] > -60]

#                 # Select only the important columns for display
#                 important_columns = ['pct_buy', 'pct_sell', 'rsi_buy', 'rsi_sell',
#                                     '# Trades', 'Win Rate [%]', 'Return [%]', 
#                                     'Max. Drawdown [%]', 'Final Cash']

#                 # Get top 25 entries from the filtered DataFrame
#                 top_final_cash = filtered_df[important_columns].head(25)

#                 # Round columns for readability
#                 top_final_cash = top_final_cash.round({
#                     'Final Cash': 2, 
#                     'Return [%]': 2, 
#                     'Max. Drawdown [%]': 2, 
#                     'Win Rate [%]': 2,
#                 })

#                 # Print the top rows in a formatted table with the "pretty" style
#                 print("---------------------------HEXABOT Rami Sayed----------------------")
#                 print(f"Highest Final Cash and Max Drawdown {row['pct_buy']} : {row['pct_sell']} - {row['rsi_buy']} : {row['rsi_sell']} ")
#                 print("-------------------------------------------------------------------")
#                 print(tabulate(top_final_cash, headers='keys', tablefmt='pretty', showindex=False))




if __name__ == "__main__":
    # Initialize the DataSQL object
    bt = DataSQL('BTCUSDT', '1h', '2020-05-01', '2024-11-01')
    cash = 1000
    
    reader = SqlReader()
    print(reader.get_tables())
    Backtest.set_db(input('Please write name of table: '))

    # Define parameter ranges
    pct_buy = np.round(np.arange(-4, 5, 0.3), 1)    # Pct buy thresholds
    pct_sell = np.round(np.arange(0, 5, 0.3), 1)   # Pct sell thresholds
    rsi_buy = np.arange(15, 30, 2)                  # RSI Buy thresholds
    rsi_sell = np.arange(75, 95, 2)                 # RSI Sell thresholds

    # Create DataFrames for each parameter
    df_pct_buy = pd.DataFrame(pct_buy, columns=['pct_buy'])
    df_pct_sell = pd.DataFrame(pct_sell, columns=['pct_sell'])
    df_rsi_buy = pd.DataFrame(rsi_buy, columns=['rsi_buy'])
    df_rsi_sell = pd.DataFrame(rsi_sell, columns=['rsi_sell'])

    # Perform cross join to create all combinations
    df_cross = df_pct_buy.merge(df_pct_sell, how='cross').merge(df_rsi_buy, how='cross').merge(df_rsi_sell, how='cross')

    # Specify the CSV file path
    csv_file_path = 'live_results.csv'

    # Initialize an empty DataFrame to collect outputs
    output_df = pd.DataFrame()

    # Initialize variable to store the last final equity
    last_final_equity = None

    # Check if CSV exists and read last row if it does
    if os.path.exists(csv_file_path):
        df_existing = pd.read_csv(csv_file_path)
        if not df_existing.empty:  # Check if df_existing is not empty
            # Remove the last three rows
            df_existing = df_existing[:-3]
            df_existing.to_csv(csv_file_path, index=False)  # Update the CSV

            # Get the last parameters used from the existing CSV
            last_row = df_existing.iloc[-1]  # Safe to access the last row now
            last_pct_buy = last_row['pct_buy']
            last_pct_sell = last_row['pct_sell']
            last_rsi_buy = last_row['rsi_buy']
            last_rsi_sell = last_row['rsi_sell']

            # Filter df_cross to only include combinations after the last recorded row
            df_cross = df_cross[(df_cross['pct_buy'] > last_pct_buy) | 
                                ((df_cross['pct_buy'] == last_pct_buy) & (df_cross['pct_sell'] > last_pct_sell)) |
                                ((df_cross['pct_buy'] == last_pct_buy) & (df_cross['pct_sell'] == last_pct_sell) & (df_cross['rsi_buy'] > last_rsi_buy)) |
                                ((df_cross['pct_buy'] == last_pct_buy) & (df_cross['pct_sell'] == last_pct_sell) & (df_cross['rsi_buy'] == last_rsi_buy) & (df_cross['rsi_sell'] > last_rsi_sell))]
        else:
            print("The existing CSV file is empty. Proceeding with all parameter combinations.")

    # Loop over each parameter combination
    for _, row in df_cross.iterrows():
        # Run the Backtest with each parameter combination
        backtest = Backtest(
            cash=cash,  # Initial cash amount used for backtest
            fees=0.001,
            rsi_buy=row['rsi_buy'],
            rsi_sell=row['rsi_sell'],
            pct_buy=row['pct_buy'],
            pct_sell=row['pct_sell'],
            tp=0,
            sl=0
        )

        # Assume `backtest.output` returns a dictionary-like structure for easy conversion
        output_series = pd.Series(backtest.output)

        # Add the current parameters to the output for reference
        output_series = pd.concat([row, output_series])

        # Get the final equity and max drawdown from the output
        current_final_equity = backtest.output.get('Final Cash')
        max_drawdown = backtest.output.get('Max. Drawdown [%]')  # Assuming this value is returned

        # Check if the final equity is different from the initial cash and has changed compared to last recorded equity
        if current_final_equity != cash and (last_final_equity is None or current_final_equity != last_final_equity):
            # Append the output to the DataFrame regardless of the max drawdown condition
            output_df = pd.concat([output_df, output_series.to_frame().T], ignore_index=True)

            # Update the last final equity
            last_final_equity = current_final_equity
            
            # Append the results to the CSV file
            output_df.to_csv(csv_file_path, mode='a', header=not pd.io.common.file_exists(csv_file_path), index=False)

            dt = datetime.now()
            if dt.minute % 2 == 0 and (18 <= dt.second <= 20):
                print("\033c")
                df = pd.read_csv(csv_file_path)

                # Sort the DataFrame by 'Final Cash' and 'Max. Drawdown [%]'
                sorted_df = df.sort_values(
                    by=['Final Cash', 'Max. Drawdown [%]'], ascending=[False, True])

                # Filter to keep only rows where Max. Drawdown [%] is greater than -60%
                filtered_df = sorted_df[sorted_df['Max. Drawdown [%]'] > -60]

                # Drop duplicates based on 'Final Cash' to get unique final cash values
                unique_final_cash_df = filtered_df.drop_duplicates(subset=['Final Cash'])

                # Select the important columns for display
                important_columns = ['pct_buy', 'pct_sell', 'rsi_buy', 'rsi_sell',
                                    '# Trades', 'Win Rate [%]', 'Return [%]',
                                    'Max. Drawdown [%]', 'Final Cash']

                # Get the top 25 entries from the unique final cash DataFrame
                top_final_cash = unique_final_cash_df[important_columns].head(25)

                # Round columns for readability
                top_final_cash = top_final_cash.round({
                    'Final Cash': 2,
                    'Return [%]': 2,
                    'Max. Drawdown [%]': 2,
                    'Win Rate [%]': 2,
                })

                # Print the top rows in a formatted table with the "pretty" style
                print("---------------------------HEXABOT Rami Sayed----------------------")
                print(f"Highest Final Cash and Max Drawdown ")
                print("-------------------------------------------------------------------")
                print(tabulate(top_final_cash, headers='keys',
                    tablefmt='pretty', showindex=False))
