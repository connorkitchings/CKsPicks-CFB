import pandas as pd
import numpy as np

def update_yards_gained(row):
    """
    Standardizes yards_gained for fumble plays to ensure consistent offensive statistics.
    """
    play_type = row['play_type']
    yards_gained = row['yards_gained']

    # Fumble return touchdowns
    if "fumble recovery (touchdown)" in play_type.lower() and yards_gained != 0:
        return 0
    # Opponent fumble recoveries
    elif "fumble recovery (opponent)" in play_type.lower():
        return 0
    # All other plays
    else:
        return yards_gained

def calculate_explosive(row):
    """
    Determines if a play qualifies as an "explosive" play based on football analytics standards.
    """
    play_type = row['play_type']
    yards_gained = row['yards_gained']
    rush_result = row['rush_result'] # Assuming rush_result is now available
    pass_attempt = row['pass_attempt'] # Assuming pass_attempt is now available

    if play_type in ['Rush', 'Rushing Touchdown', 'Fumble Recovery (Own)', 'Pass', 'Pass Reception', 'Pass Incompletion', 'Passing Touchdown', 'Sack', 'Safety']:
        if (rush_result == 1) and (yards_gained >= 15):
            return 1
        if (pass_attempt == 1) and (yards_gained >= 20):
            return 1
        else:
            return 0
    elif play_type in ['Fumble Recovery (Opponent)', 'Fumble Return Touchdown', 'Pass Interception Return', 'Interception Return Touchdown', 'Safety', 'Interception']:
        return 0
    else:
        return None

def calculate_play_success(row):
    """
    Determines if a play was "successful" using down-and-distance success rate criteria.
    """
    down = row['down']
    yards_gained = row['yards_gained']
    yards_to_first = row['yards_to_first']
    play_type = row['play_type']
    turnover = row['turnover'] # Assuming turnover is now available
    penalty = row['penalty'] # Assuming penalty is now available

    if play_type in ['Rush', 'Rushing Touchdown', 'Fumble Recovery (Own)', 'Pass', 'Pass Reception', 'Pass Incompletion', 'Passing Touchdown', 'Sack', 'Safety']:
        if yards_to_first == 0:
            if down == 1 and yards_gained >= (0.5 * row['yards_to_goal']):
                return 1
            if down == 2 and yards_gained >= (0.7 * row['yards_to_goal']):
                return 1
            if down == 3 and yards_gained >= row['yards_to_goal']:
                return 1
            if down == 4 and yards_gained >= row['yards_to_goal']:
                return 1
            else:
                return 0
        elif yards_to_first > 0:
            if down == 1 and yards_gained >= (0.5 * yards_to_first):
                return 1
            if down == 2 and yards_gained >= (0.7 * yards_to_first):
                return 1
            if down == 3 and yards_gained >= yards_to_first:
                return 1
            if down == 4 and yards_gained >= yards_to_first:
                return 1
            # Additional goal line check from notebook
            if down == 1 and yards_gained >= (0.5 * row['yards_to_goal']):
                return 1
            if down == 2 and yards_gained >= (0.7 * row['yards_to_goal']):
                return 1
            if down == 3 and yards_gained >= row['yards_to_goal']:
                return 1
            if down == 4 and yards_gained >= row['yards_to_goal']:
                return 1
            else:
                return 0
        else:
            return 0
    elif turnover == 1:
        return 0
    elif penalty == 1:
        return None
    else:
        return None

def calculate_time_features(data):
    """
    Calculates time remaining features for each play.
    Assumes 15-minute quarters for regulation play.
    """
    df = data.copy()
    # Sort the data first
    df = df.sort_values(by=['season', 'week', 'game_id', 'quarter', 'drive_number', 'play_number'], ascending=[True, True, True, True, True, True]).reset_index(drop=True)

    # Validate clock_minutes and clock_seconds
    if df['clock_minutes'].max() > 15 or df['clock_seconds'].max() >= 60:
        print("Warning: Some clock values seem to be out of range.")

    # Calculate clock_minutes_in_secs
    df['clock_minutes_in_secs'] = np.where(
        df['quarter'] <= 4,
        (4 - df['quarter']) * 15 * 60 + (df['clock_minutes'] * 60),
        0  # For overtime periods
    )

    # Add clock seconds to get total time remaining
    df['time_remaining_after'] = df['clock_minutes_in_secs'] + df['clock_seconds']

    # Calculate time remaining before the play
    df['time_remaining_before'] = df.groupby('game_id')['time_remaining_after'].shift(1)
    df.loc[(df['drive_number'] == 1) & (df['play_number'] == 1), 'time_remaining_before'] = 3600

    # Calculate play duration
    df['play_duration'] = df['time_remaining_before'] - df['time_remaining_after']

    # Validate results
    if df['play_duration'].min() < 0:
        print("Warning: Some play durations are negative. This might indicate an issue with the time calculation.")
        
    # Assuming 'penalty', 'st', 'twopoint' are already calculated binary columns
    df.loc[df['penalty'] == 1, 'play_duration'] = None
    df.loc[((df['st'] == 1)|(df['twopoint'] == 1)), 'play_duration'] = None
    df.loc[df['play_duration'] <= 0, 'play_duration'] = None
    df.loc[df['play_duration'] >= 60, 'play_duration'] = None # The data is that bad. 10% of all the play durations turn out this way. Nothing I can do. 
    
    return df

def allplays_to_byplay(data):
    """
    Transforms raw play-by-play data into a comprehensive analytics-ready dataset.
    """
    df = data.copy()

    # Constants (from API_Functions.ipynb)
    FBS_list = ['SEC','American Athletic','FBS Independents','Big Ten','Conference USA','Big 12','Mid-American',
                'ACC','Sun Belt','Pac-12','Mountain West']
    st_kickoffs = ['Kickoff', 'Kickoff Return (Offense)', 'Kickoff Return Touchdown']
    st_punts = ['Punt', 'Blocked Punt', 'Punt Return Touchdown', 'Blocked Punt Touchdown']
    st_fg = ['Field Goal Good', 'Field Goal Missed', 'Blocked Field Goal', 'Missed Field Goal Return', 'Missed Field Goal Return Touchdown', 'Blocked Field Goal Touchdown']
    st_extrapoint = ['Extra Point Good', 'Extra Point Missed']
    twopoint_list = ['Two Point Pass', 'Two Point Rush', 'Defensive 2pt Conversion']
    st_list = st_kickoffs + st_punts + st_fg + st_extrapoint
    endofdrive = ['Punt', 'Field Goal Good', 'Field Goal Missed', 'Blocked Field Goal', 'Blocked Punt', 'Punt Return Touchdown', 'Blocked Punt Touchdown',
                  'Missed Field Goal Return', 'Blocked Field Goal Touchdown', 'Missed Field Goal Return Touchdown']
    turnover_list = ['Interception', 'Interception Return Touchdown', 'Pass Interception Return', 'Fumble Recovery (Opponent)', 'Fumble Return Touchdown']
    rushattempt_list = ['Rush', 'Rushing Touchdown']
    rushresult_list = ['Rush', 'Rushing Touchdown', 'Sack', 'Safety']
    dropback_list = ['Pass', 'Interception', 'Interception Return Touchdown', 'Pass Interception Return', 'Passing Touchdown', 'Pass Incompletion',
                     'Pass Reception', 'Sack']
    passattempt_list = ['Pass', 'Pass Completion', 'Interception', 'Interception Return Touchdown', 'Pass Interception Return', 'Passing Touchdown', 'Pass Incompletion',
                        'Pass Reception']
    completion_list = ['Pass Reception','Pass Completion','Pass', 'Passing Touchdown']
    playtype_delete = ['Timeout', 'Uncategorized', 'placeholder', 'End Period']
    havoc_list = ['Fumble Recovery (Opponent)', 'Fumble Return Touchdown', 'Fumble Recovery (Own)', 'Pass Incompletion',
                  'Interception', 'Interception Return Touchdown', 'Pass Interception Return']

    # Basic Columns
    df['relative_score'] = df['offense_score'] - df['defense_score']
    df['half'] = np.select([df['quarter'].isin([1,2]), df['quarter'].isin([3,4])], [1, 2], default=3)
    df['home_away'] = np.where(df['offense'] == df['home'], 'home', 'away')

    # Penalty Categorization (refined from API_Functions.ipynb)
    df['penalty'] = (df['play_type'] == 'Penalty').astype(int)
    df['defensive_penalty'] = ((df['play_type'] == 'Penalty') & (df['yards_gained'] > 0)).astype(int)
    df['offensive_penalty'] = ((df['play_type'] == 'Penalty') & (df['yards_gained'] < 0)).astype(int)

    # Binary Play Type Indicators (refined from API_Functions.ipynb)
    binary_columns = {
        'st_kickoff': st_kickoffs,
        'st_punt': st_punts,
        'st_fg': st_fg,
        'st': st_list,
        'endofdrive': endofdrive,
        'twopoint': twopoint_list,
        'turnover': turnover_list,
        'rush_attempt': rushattempt_list,
        'rush_result': rushresult_list, # New: rush_result
        'dropback': dropback_list,
        'pass_attempt': passattempt_list
    }
    
    for col, play_types in binary_columns.items():
        df[col] = df['play_type'].isin(play_types).astype(int)

    # Situational Indicators
    df['red_zone'] = (df['yards_to_goal'] <= 20).astype(int)
    df['eckel'] = ((df['yards_to_goal'] < 40) & (df['down'] == 1)).astype(int)

    # Yards and Performance Metrics
    df['updated_yards_gained'] = df.apply(update_yards_gained, axis=1)
    df['TFL'] = ((df['penalty'] == 0) & (df['updated_yards_gained'] < 0)).astype(int)
    df['sack'] = (df['play_type'] == 'Sack').astype(int)
    df['completion'] = (df['play_type'].isin(completion_list)).astype(int) # Refined

    # Calculate success, explosive, opportunity
    df['success'] = df.apply(calculate_play_success, axis=1)
    df['explosive'] = df.apply(calculate_explosive, axis=1)
    df['success_yards'] = np.where(df['success'] == 1, df['updated_yards_gained'], 0)
    df['explosive_yards'] = np.where(df['explosive'] == 1, df['updated_yards_gained'], 0)
    df['stuff'] = ((df['rush_attempt'] == 1) & (df['updated_yards_gained'] <= 0)).astype(int)

    # Calculate havoc (refined from API_Functions.ipynb)
    df['havoc'] = (df['play_type'].isin(havoc_list) | (df['updated_yards_gained'] < 0)).astype(int)
    df.loc[df['penalty'] == 1, 'havoc'] = 0 # Important correction
    
    # Create third and fourth down conversion columns
    df['thirddown_conversion'] = np.where(df['down'] == 3, 
                                                   (np.where(df['success'] == 1, 1, 0)), 
                                                   None)
    df['fourthdown_conversion'] = np.where(df['down'] == 4, 
                                                   (np.where(df['success'] == 1, 1, 0)), 
                                                   None)

    # Rename updated_yards_gained to yards_gained
    df = df.drop(columns=['yards_gained']).rename(columns={'updated_yards_gained': 'yards_gained'})
    
    # Sort values
    df = df.sort_values(by=['season', 'week', 'game_id', 'quarter','drive_number','play_number'])

    # Calculate time remaining (using the new calculate_time_features)
    df = calculate_time_features(df)
    
    # Efficient garbage time calculation
    def calculate_garbage_time(df_inner):
        # Initialize garbage column with False
        df_inner['garbage'] = False
        
        # No garbage time in first half
        second_half = df_inner['quarter'] > 2
        
        # Third quarter garbage time
        df_inner.loc[second_half & (df_inner['quarter'] == 3) & (abs(df_inner['relative_score']) >= 35), 'garbage'] = True
        
        # Fourth quarter garbage time
        fourth_quarter = second_half & (df_inner['quarter'] == 4)
        df_inner.loc[fourth_quarter & (abs(df_inner['relative_score']) >= 27), 'garbage'] = True
        
        return df_inner['garbage'].astype(int)

    # Apply garbage time calculation
    df['garbage'] = calculate_garbage_time(df)
    
    # Categorize field position
    df['field_position_bin'] = pd.cut(
        df['yard_line'],
        bins=[0, 20, 50, 80, 100],
        labels=['Own Red Zone', 'Own', 'Opponent', 'Red Zone']
    )
    
    # Define passing down conditions
    df['passing_down'] = np.where(
        ((df['down'] == 2) & (df['yards_to_first'] >= 8)) |
        ((df['down'].isin([3, 4])) & (df['yards_to_first'] >= 5)),
        1, 0
    )
    
    # Drop unnecessary columns and filter out certain play types
    # This column order is based on the notebook's final output columns
    column_order = ['season', 'week', 'game_id', 'offense', 'defense', 'home_away', 'relative_score', 
                    'offense_score','defense_score', 'half', 'quarter', 'offense_timeouts', 'defense_timeouts', 
                    'drive_id', 'drive_number', 'play_number', 'garbage','yard_line', 'yards_to_goal', 'adj_yd_line', 'field_position_bin', 'down', 'yards_to_first', 
                    'passing_down', 'red_zone', 'eckel', 'scoring', 'play_type', 'play_text', 'penalty', 'offensive_penalty', 'defensive_penalty',
                    'st', 'st_kickoff', 'st_punt', 'st_fg', 'endofdrive', 'twopoint', 'turnover',
                    'rush_attempt','rush_result', 'dropback', 'pass_attempt', 'yards_gained', 'ppa', 'TFL', 'sack', 'completion', 'success', 'success_yards', 
                    'explosive', 'explosive_yards', 'stuff', 'havoc', 'thirddown_conversion', 'fourthdown_conversion',
                    'clock_minutes', 'clock_minutes_in_secs', 'clock_seconds','time_remaining_after', 'time_remaining_before', 'play_duration']
    df = df[column_order].copy()
    df = df[~df['play_type'].isin(playtype_delete)].copy()
    df['ppa'] = pd.to_numeric(df['ppa'], errors='coerce')
    
    # Because I have to put them somewhere (from notebook)
    df.loc[df['play_type'].isin(['Fumble Recovery (Own)', 'Fumble Recovery (Opponent)']), 'rush_attempt'] = 1
    df.loc[df['play_type'].isin(['Fumble Recovery (Own)', 'Fumble Recovery (Opponent)']), 'rush_result'] = 1
    df.loc[df['play_type'].isin(['Fumble Recovery (Opponent)']), 'yards_gained'] = 0

    return df

def apply_updates_to_dataframe(df, conditions_and_updates):
    """
    Applies specific corrections to individual plays or drives in the DataFrame based on predefined conditions.
    """
    for condition, updates in conditions_and_updates:
        game_id, drive_number, *play_number = condition
        if not play_number:
            # If play_number is not provided in the condition, apply the updates to all rows matching game_id and drive_number
            condition_mask = (df['game_id'] == game_id) & (df['drive_number'] == drive_number)
        else:
            play_number = play_number[0]  # Extract the play_number from the list
            # Apply the updates only to rows matching all conditions
            condition_mask = (df['game_id'] == game_id) & (df['drive_number'] == drive_number) & (df['play_number'] == play_number)
        df.loc[condition_mask, list(updates.keys())] = list(updates.values())
    return df

conditions_and_updates = [
    ((400937467, 1, 5), {'yards_gained': 15, 'play_type': 'Penalty'}),
    ((400547851, 11, 6), {'yards_gained': 15, 'play_type': 'Penalty'}),
    ((400547737, 9, 1), {'yards_to_first': 1}),
    ((400547737, 9, 2), {'yard_line': 2, 'yards_to_goal': 98, 'yards_to_first': 9, 'yards_gained': -1, 'adj_yd_line': 98}),
    ((400547737, 9, 3), {'yards_to_first': 10}),
    ((400547739, 11, 14), {'yards_gained': -5}),
    ((400547739, 11, 15), {'yard_line': 82, 'yards_to_goal': 18, 'yards_to_first': 18, 'adj_yd_line': 18}),
    ((400547739, 11, 16), {'yard_line': 82, 'yards_to_goal': 18, 'yards_to_first': 18, 'adj_yd_line': 18}),
    ((400869843, 27, 9), {'yards_gained': -5}),
    ((400869843, 27, 10), {'yard_line': 78, 'yards_to_goal': 22}),
    ((401237102, 4), {'offense': 'Texas A&M', 'defense': 'Florida'}),
    ((401237102, 4, 8), {'play_number': 5}),
    ((401237102, 4, 9), {'play_number': 6}),
    ((401237102, 4, 10), {'play_number': 7}),
    ((401237102, 4, 11), {'play_number': 8}),
    ((401237102, 4, 12), {'play_number': 9}),
    ((401237102, 4, 13), {'play_number': 10}),
    ((401237102, 4, 14), {'play_number': 11}),
    ((401237102, 4, 15), {'play_number': 12}),
    ((401237102, 4, 16), {'play_number': 13}),
    ((401237102, 4, 17), {'play_number': 14}),
    ((401237102, 4, 18), {'play_number': 15}),
    ((401237102, 4, 29), {'play_number': 16}),
    ((400869850, 26, 15), {'yards_gained': -5}),
    ((401013353, 23, 4), {'yards_gained': -5}),
    ((400869264, 9, 1), {'yards_gained': -5}),
    ((401114260, 11, 5), {'yards_gained': -5}),
    ((401282206, 9, 6), {'yards_gained': -15}),
    ((401405102, 14, 4), {'yards_gained': -15}),
    ((401282189, 6, 7), {'yards_gained': -15}),
    ((401309577, 22, 1), {'yards_gained': -15}),
    ((400548020, 16, 10), {'yards_gained': -5}),
    ((401403927, 9, 3), {'yards_gained': -15}),
    ((400787353, 3, 5), {'yards_gained': -5}),
    ((400869721, 19, 5), {'yards_gained': -15}),
    ((401310733, 6, 8), {'yards_gained': 0}),
    ((401287949, 4, 3), {'yards_gained': -9}),
    ((401309639, 19, 5), {'yards_gained': 0}),
    ((401282215, 26, 10), {'yards_gained': 0}),
    ((401119278, 26, 7), {'yards_gained': 0}),
    ((401121957, 28, 4), {'yards_gained': -10}),
    ((400941829, 25, 2), {'play_type': 'Penalty', 'yards_gained': -10}),
    ((400869041, 18, 8), {'yards_gained': -9}),
    ((400547743, 21, 3), {'yards_gained': 15}),
    ((401117876, 8, 5), {'yards_gained': 0}),
    ((401022561, 20, 11), {'yards_gained': 15}),
    ((401643724, 22, 15), {'yard_line': 25, 'yards_to_goal': 25, 'yards_to_first': 25, 'adj_yd_line': 25}), # Added 10/14/24
]