# Error Analysis 2024

**Total Games**: 735
**Model MAE**: 12.90
**Market MAE**: 12.15
**Model RMSE**: 16.50

## Error by Spread Magnitude
| spread_category       |   ('abs_error', 'mean') |   ('abs_error', 'count') |   ('market_abs_error', 'mean') |   ('market_abs_error', 'count') |   ('error', 'mean') |   ('error', 'count') |
|:----------------------|------------------------:|-------------------------:|-------------------------------:|--------------------------------:|--------------------:|---------------------:|
| Away Fav (-7 to -14)  |                 13.8416 |                       76 |                        13.7303 |                              76 |           -4.61577  |                   76 |
| Close Game (+/- 7)    |                 13.2016 |                      348 |                        12.0489 |                             348 |           -4.4288   |                  348 |
| Heavy Away Fav (<-14) |                 13.1502 |                       48 |                        12.1354 |                              48 |           -4.01295  |                   48 |
| Heavy Home Fav (>14)  |                 11.9579 |                      158 |                        11.4652 |                             158 |           -5.05022  |                  158 |
| Home Fav (7-14)       |                 12.5066 |                      105 |                        12.4048 |                             105 |           -0.748513 |                  105 |

## Error by Season Phase
| week_category   |   abs_error |   market_abs_error |
|:----------------|------------:|-------------------:|
| Early (1-4)     |     13.681  |            13.0914 |
| Late (10+)      |     12.8161 |            12.2466 |
| Mid (5-9)       |     12.4779 |            11.4463 |

## Error by Model-Market Disagreement
| disagreement   |   ('abs_error', 'mean') |   ('abs_error', 'count') |   ('market_abs_error', 'mean') |   ('market_abs_error', 'count') |   ('edge', 'mean') |   ('edge', 'count') |
|:---------------|------------------------:|-------------------------:|-------------------------------:|--------------------------------:|-------------------:|--------------------:|
| Low (<2.5)     |                 13.0508 |                      294 |                        13.0731 |                             294 |          -0.169242 |                 294 |
| Med (2.5-5)    |                 11.9225 |                      166 |                        11.6988 |                             166 |          -1.96239  |                 166 |
| High (>5)      |                 13.3229 |                      275 |                        11.4455 |                             275 |          -6.77329  |                 275 |

## Top 10 Worst Predictions (Model Misses)
|   week | home_team             | away_team          |   model_home_adv |   market_home_adv |   actual_margin |    error |   abs_error |
|-------:|:----------------------|:-------------------|-----------------:|------------------:|----------------:|---------:|------------:|
|      5 | UConn                 | Buffalo            |         -5.78269 |               6   |              44 | -49.7827 |     49.7827 |
|      2 | Florida International | Central Michigan   |        -13.3535  |              -3.5 |              36 | -49.3535 |     49.3535 |
|      3 | Purdue                | Notre Dame         |         -9.71382 |              -7   |             -59 |  49.2862 |     49.2862 |
|     14 | Tulsa                 | Florida Atlantic   |          2.1347  |               1   |             -47 |  49.1347 |     49.1347 |
|      3 | South Alabama         | Northwestern State |         28.3779  |              36.5 |              77 | -48.6221 |     48.6221 |
|     14 | Indiana               | Purdue             |         18.6916  |              29   |              66 | -47.3084 |     47.3084 |
|      4 | BYU                   | Kansas State       |        -17.8797  |              -7   |              29 | -46.8797 |     46.8797 |
|     12 | Utah State            | Hawai'i            |         -1.17808 |              -2.5 |              45 | -46.1781 |     46.1781 |
|      8 | Indiana               | Nebraska           |          3.8885  |               6.5 |              49 | -45.1115 |     45.1115 |
|      7 | Maryland              | Northwestern       |         17.85    |              11   |             -27 |  44.85   |     44.85   |

