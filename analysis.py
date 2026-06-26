import pandas as pd

# Load the data
matches = pd.read_csv('data/matches.csv')
deliveries = pd.read_csv('data/deliveries.csv')

# Get a feel for the data
print("=== MATCHES ===")
print(f"Total matches: {len(matches)}")
print(f"Seasons covered: {matches['season'].min()} to {matches['season'].max()}")
print(f"Columns: {list(matches.columns)}")

print("\n=== DELIVERIES ===")
print(f"Total balls bowled: {len(deliveries)}")
print(f"Columns: {list(deliveries.columns)}")

print("\n=== FIRST 3 MATCHES ===")
print(matches.head(3))

print("\n=== MISSING VALUES IN MATCHES ===")
print(matches.isnull().sum())

# ── CLEANING ──────────────────────────────────────────

# 1. Drop abandoned matches (no winner)
matches = matches.dropna(subset=['winner'])
print(f"After dropping no-result matches: {len(matches)} matches")

# 2. Fix season column — make everything a clean year
matches['season'] = matches['season'].astype(str).str[:4].astype(int)
print(f"Seasons: {sorted(matches['season'].unique())}")

# 3. Fix team name inconsistencies (teams got renamed over the years)
team_rename = {
    'Delhi Daredevils': 'Delhi Capitals',
    'Deccan Chargers': 'Sunrisers Hyderabad',
    'Punjab Kings': 'Kings XI Punjab',
    'Rising Pune Supergiant': 'Rising Pune Supergiants',
}
for col in ['team1', 'team2', 'winner', 'toss_winner']:
    matches[col] = matches[col].replace(team_rename)

# 4. Convert date to datetime
matches['date'] = pd.to_datetime(matches['date'])

# 5. Fill missing city from venue
venue_city_map = matches.dropna(subset=['city']).set_index('venue')['city'].to_dict()
matches['city'] = matches.apply(
    lambda r: venue_city_map.get(r['venue'], 'Unknown') if pd.isna(r['city']) else r['city'],
    axis=1
)

print("\n=== AFTER CLEANING ===")
print(f"Remaining nulls in key columns:")
print(matches[['city','winner','season']].isnull().sum())
print("\nData is clean and ready for analysis!")

import sqlite3

# ── ANALYSIS ──────────────────────────────────────────

# 1. Win rate by team
win_counts = matches['winner'].value_counts().reset_index()
win_counts.columns = ['team', 'wins']
total_played = pd.concat([matches['team1'], matches['team2']]).value_counts().reset_index()
total_played.columns = ['team', 'played']
win_rate = win_counts.merge(total_played, on='team')
win_rate['win_rate_%'] = (win_rate['wins'] / win_rate['played'] * 100).round(1)
win_rate = win_rate.sort_values('win_rate_%', ascending=False)
print("=== WIN RATE BY TEAM ===")
print(win_rate.to_string(index=False))

# 2. Toss impact — does winning toss help?
matches['toss_win_match_win'] = matches['toss_winner'] == matches['winner']
toss_impact = matches['toss_win_match_win'].value_counts(normalize=True) * 100
print("\n=== TOSS IMPACT ===")
print(f"Won toss AND match:  {toss_impact[True]:.1f}%")
print(f"Won toss, lost match: {toss_impact[False]:.1f}%")

# 3. Toss decision — bat or field?
print("\n=== TOSS DECISION PREFERENCE ===")
print(matches['toss_decision'].value_counts())

# 4. Top 10 batsmen (total runs)
top_batsmen = (deliveries.groupby('batter')['batsman_runs']
               .sum()
               .sort_values(ascending=False)
               .head(10)
               .reset_index())
top_batsmen.columns = ['batsman', 'total_runs']
print("\n=== TOP 10 BATSMEN ===")
print(top_batsmen.to_string(index=False))

# 5. Top 10 bowlers (total wickets)
wickets = deliveries[deliveries['is_wicket'] == 1]
top_bowlers = (wickets.groupby('bowler')['is_wicket']
               .sum()
               .sort_values(ascending=False)
               .head(10)
               .reset_index())
top_bowlers.columns = ['bowler', 'wickets']
print("\n=== TOP 10 BOWLERS ===")
print(top_bowlers.to_string(index=False))

# ── SQL ANALYSIS ───────────────────────────────────────
# This is what earns you the SQL line on your resume

conn = sqlite3.connect(':memory:')
matches.to_sql('matches', conn, index=False, if_exists='replace')
deliveries.to_sql('deliveries', conn, index=False, if_exists='replace')

# SQL Query 1 — wins per team per season
sql1 = '''
    SELECT season, winner AS team, COUNT(*) AS wins
    FROM matches
    GROUP BY season, winner
    ORDER BY season, wins DESC
'''
print("\n=== SQL: WINS PER TEAM PER SEASON (first 15 rows) ===")
print(pd.read_sql(sql1, conn).head(15).to_string(index=False))

# SQL Query 2 — which city hosts most matches
sql2 = '''
    SELECT city, COUNT(*) AS matches_hosted
    FROM matches
    GROUP BY city
    ORDER BY matches_hosted DESC
    LIMIT 8
'''
print("\n=== SQL: TOP CITIES BY MATCHES HOSTED ===")
print(pd.read_sql(sql2, conn).to_string(index=False))

conn.close()
print("\n✅ Full analysis complete!")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import os

os.makedirs('charts', exist_ok=True)

plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = '#f8f8f8'
plt.rcParams['font.family'] = 'sans-serif'

# ── CHART 1: Win Rate by Team ──────────────────────────
fig, ax = plt.subplots(figsize=(12, 7))
colors = ['#1a56db' if w >= 50 else '#e74c3c' for w in win_rate['win_rate_%']]
bars = ax.barh(win_rate['team'], win_rate['win_rate_%'], color=colors, edgecolor='none')
ax.axvline(50, color='gray', linestyle='--', linewidth=1, alpha=0.7, label='50% mark')
for bar, val in zip(bars, win_rate['win_rate_%']):
    ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
            f'{val}%', va='center', fontsize=10)
ax.set_xlabel('Win Rate (%)', fontsize=12)
ax.set_title('IPL Team Win Rates (2007–2024)', fontsize=15, fontweight='bold', pad=15)
ax.legend()
ax.set_xlim(0, 75)
plt.tight_layout()
plt.savefig('charts/01_win_rate_by_team.png', dpi=150)
plt.close()
print("✅ Chart 1 saved")

# ── CHART 2: Toss Impact ──────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 5))

# Pie — toss win vs loss
axes[0].pie(
    [toss_impact[True], toss_impact[False]],
    labels=['Won toss\n& match', 'Won toss\nlost match'],
    colors=['#1a56db', '#e74c3c'],
    autopct='%1.1f%%',
    startangle=90,
    textprops={'fontsize': 12}
)
axes[0].set_title('Does Winning the Toss Help?', fontsize=13, fontweight='bold')

# Bar — toss decision preference
decision_counts = matches['toss_decision'].value_counts()
axes[1].bar(decision_counts.index, decision_counts.values,
            color=['#1a56db', '#f39c12'], edgecolor='none', width=0.5)
for i, (idx, val) in enumerate(decision_counts.items()):
    axes[1].text(i, val + 5, str(val), ha='center', fontsize=12, fontweight='bold')
axes[1].set_title('Toss Decision: Bat or Field First?', fontsize=13, fontweight='bold')
axes[1].set_ylabel('Number of matches')
axes[1].set_ylim(0, 800)

plt.suptitle('Toss Analysis — IPL 2007–2024', fontsize=15, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('charts/02_toss_analysis.png', dpi=150, bbox_inches='tight')
plt.close()
print("✅ Chart 2 saved")

# ── CHART 3: Top 10 Batsmen ───────────────────────────
fig, ax = plt.subplots(figsize=(11, 6))
bars = ax.barh(top_batsmen['batsman'], top_batsmen['total_runs'],
               color='#1a56db', edgecolor='none')
for bar, val in zip(bars, top_batsmen['total_runs']):
    ax.text(bar.get_width() + 50, bar.get_y() + bar.get_height()/2,
            f'{val:,}', va='center', fontsize=10)
ax.set_xlabel('Total Runs', fontsize=12)
ax.set_title('Top 10 Run Scorers in IPL History', fontsize=15, fontweight='bold', pad=15)
ax.set_xlim(0, 9500)
ax.invert_yaxis()
plt.tight_layout()
plt.savefig('charts/03_top_batsmen.png', dpi=150)
plt.close()
print("✅ Chart 3 saved")

# ── CHART 4: Top 10 Bowlers ───────────────────────────
fig, ax = plt.subplots(figsize=(11, 6))
bars = ax.barh(top_bowlers['bowler'], top_bowlers['wickets'],
               color='#e74c3c', edgecolor='none')
for bar, val in zip(bars, top_bowlers['wickets']):
    ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
            f'{val}', va='center', fontsize=10)
ax.set_xlabel('Total Wickets', fontsize=12)
ax.set_title('Top 10 Wicket Takers in IPL History', fontsize=15, fontweight='bold', pad=15)
ax.set_xlim(0, 250)
ax.invert_yaxis()
plt.tight_layout()
plt.savefig('charts/04_top_bowlers.png', dpi=150)
plt.close()
print("✅ Chart 4 saved")

# ── CHART 5: Wins per season (top 5 teams) ───────────────
# reconnect since we closed earlier
conn2 = sqlite3.connect(':memory:')
matches.to_sql('matches', conn2, index=False, if_exists='replace')
deliveries.to_sql('deliveries', conn2, index=False, if_exists='replace')
season_wins = pd.read_sql_query(
    '''SELECT season, winner AS team, COUNT(*) AS wins 
       FROM matches 
       GROUP BY season, winner 
       ORDER BY season, wins DESC''',
    conn2
)
top5_teams = win_rate.head(5)['team'].tolist()
season_wins_top5 = season_wins[season_wins['team'].isin(top5_teams)]

fig, ax = plt.subplots(figsize=(14, 6))
colors_map = {
    'Gujarat Titans': '#1a56db',
    'Chennai Super Kings': '#f39c12',
    'Lucknow Super Giants': '#8e44ad',
    'Mumbai Indians': '#1abc9c',
    'Kolkata Knight Riders': '#e74c3c'
}
for team in top5_teams:
    data = season_wins_top5[season_wins_top5['team'] == team]
    ax.plot(data['season'], data['wins'], marker='o', linewidth=2,
            label=team, color=colors_map.get(team, '#333'))

ax.set_xlabel('Season', fontsize=12)
ax.set_ylabel('Wins', fontsize=12)
ax.set_title('Season-wise Wins — Top 5 IPL Teams', fontsize=15, fontweight='bold', pad=15)
ax.legend(loc='upper left', fontsize=10)
ax.set_xticks(season_wins_top5['season'].unique())
ax.tick_params(axis='x', rotation=45)
plt.tight_layout()
plt.savefig('charts/05_season_wins_top5.png', dpi=150)
plt.close()
conn2.close()
print("✅ Chart 5 saved")

print("\n🎉 All 5 charts saved to charts/ folder!")