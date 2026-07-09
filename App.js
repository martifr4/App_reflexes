import { useState, useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Dimensions, Vibration, ScrollView } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const { width, height } = Dimensions.get('window');
const TOTAL_LEVELS = 10;
const TARGETS_PER_LEVEL = 10;
const LEVEL_LEADERBOARD_KEY = '@reflex_level_leaderboard';
const GLOBAL_LEADERBOARD_KEY = '@reflex_global_leaderboard';
const FASTEST_TIME_KEY = '@reflex_fastest_time';

export default function App() {
  const [screen, setScreen] = useState('menu');
  const [level, setLevel] = useState(1);
  const [score, setScore] = useState(0);
  const [targets, setTargets] = useState([]);
  const [levelStats, setLevelStats] = useState({ hits: 0, misses: 0, hitTimes: [], fastest: 9999 });
  const [allLevelStats, setAllLevelStats] = useState([]);
  const [levelLeaderboards, setLevelLeaderboards] = useState({});
  const [globalLeaderboard, setGlobalLeaderboard] = useState([]);
  const [currentLevelRank, setCurrentLevelRank] = useState(null);
  const [isFullRun, setIsFullRun] = useState(true);
  const [globalFastest, setGlobalFastest] = useState(9999);
  const [lastTapTime, setLastTapTime] = useState(0);
  const spawnedCountRef = useRef(0);
  const spawnTimeRef = useRef(null);
  const timeoutRefs = useRef({});
  const levelEndingRef = useRef(false); // FIX: guards against finishing a level twice
  const globalFastestRef = useRef(9999); // FIX: read/write fastest without stale closures
  const playerName = 'You';

  useEffect(() => { loadLeaderboards(); loadFastest(); }, []);

  // FIX: clear every pending timer when the component unmounts so timers don't fire on a dead component
  useEffect(() => {
    return () => {
      clearTimeout(spawnTimeRef.current);
      Object.values(timeoutRefs.current).forEach(clearTimeout);
    };
  }, []);

  const loadFastest = async () => {
    const data = await AsyncStorage.getItem(FASTEST_TIME_KEY);
    if(data) {
      const val = parseInt(data);
      setGlobalFastest(val);
      globalFastestRef.current = val;
    }
  }

  const saveFastest = async (time) => {
    // FIX: compare against the ref (always current) instead of the possibly-stale state value
    if(time < globalFastestRef.current){
      globalFastestRef.current = time;
      setGlobalFastest(time);
      await AsyncStorage.setItem(FASTEST_TIME_KEY, time.toString());
    }
  }

  const getSpawnInterval = (lvl) => Math.max(200, 2000 - (lvl - 1) * 200);
  const getTimeToLive = (lvl) => getSpawnInterval(lvl) * 1.5;

  const spawnTarget = (currentLvl) => {
    if (spawnedCountRef.current >= TARGETS_PER_LEVEL) return;
    const size = 80;
    const x = Math.random() * (width - size);
    const y = Math.random() * (height - 250) + 120;
    const id = Date.now() + Math.random();
    const spawnTime = Date.now();
    const ttl = getTimeToLive(currentLvl);

    setTargets(t => [...t, { id, x, y, size, spawnTime, ttl }]);
    spawnedCountRef.current += 1;

    timeoutRefs.current[id] = setTimeout(() => {
      setLevelStats(s => {
        const newS = {...s, misses: s.misses + 1};
        checkLevelEnd(newS); // check with the updated stats
        return newS;
      });
      setTargets(t => t.filter(x => x.id !== id));
      delete timeoutRefs.current[id];
    }, ttl);

    // Only schedule the next spawn if we still have targets left to spawn.
    if (spawnedCountRef.current < TARGETS_PER_LEVEL) {
      spawnTimeRef.current = setTimeout(() => spawnTarget(currentLvl), getSpawnInterval(currentLvl));
    }
  };

  // FIX: only end once, and hand the final stats straight to finishLevel so it
  // doesn't read a stale `levelStats` closure (which dropped the last target).
  const checkLevelEnd = (currentStats) => {
    const totalDone = currentStats.hits + currentStats.misses;
    if (totalDone >= TARGETS_PER_LEVEL && !levelEndingRef.current) {
      levelEndingRef.current = true;
      clearTimeout(spawnTimeRef.current);
      Object.values(timeoutRefs.current).forEach(clearTimeout); // clear any stragglers
      timeoutRefs.current = {};
      setTimeout(() => finishLevel(currentStats), 300);
    }
  }

  const handleTap = (target) => {
    Vibration.vibrate(20);
    clearTimeout(timeoutRefs.current[target.id]);
    delete timeoutRefs.current[target.id];

    const reactionTime = Date.now() - target.spawnTime;
    setLastTapTime(reactionTime);
    saveFastest(reactionTime); // FIX: side effect lives outside the state updater

    setLevelStats(s => {
      const newFastest = Math.min(s.fastest, reactionTime);
      const newS = {...s, hits: s.hits + 1, hitTimes: [...s.hitTimes, reactionTime], fastest: newFastest};
      checkLevelEnd(newS); // check with the updated stats
      return newS;
    });
    setScore(s => s + 1);
    setTargets(t => t.filter(x => x.id !== target.id));
  };

  // FIX: receives the complete final stats instead of reading stale state
  const finishLevel = async (finalStats) => {
    clearTimeout(spawnTimeRef.current);
    Object.values(timeoutRefs.current).forEach(clearTimeout);
    timeoutRefs.current = {};

    const { hits, misses, hitTimes, fastest } = finalStats;
    const avgHit = hits > 0 ? Math.round(hitTimes.reduce((a,b) => a+b,0)/hits) : 9999;
    const totalTimes = [...hitTimes, ...Array(misses).fill(getTimeToLive(level))];
    const totalAvg = Math.round(totalTimes.reduce((a,b) => a+b,0)/TARGETS_PER_LEVEL);

    const newLevelEntry = { name: playerName, avg: totalAvg, hits, misses };
    const updatedLevelLB = {...levelLeaderboards };
    const thisLevelLB = [...(updatedLevelLB[level] || []), newLevelEntry].sort((a,b) => a.avg - b.avg).slice(0, 10);
    updatedLevelLB[level] = thisLevelLB;
    setLevelLeaderboards(updatedLevelLB);
    await AsyncStorage.setItem(LEVEL_LEADERBOARD_KEY, JSON.stringify(updatedLevelLB));

    // FIX: identify our own entry by reference so a prior run with the same avg can't be matched
    const idx = thisLevelLB.indexOf(newLevelEntry);
    setCurrentLevelRank(idx >= 0 ? idx + 1 : null);
    setAllLevelStats(prev => [...prev, {level, hits, misses, avgHit, totalAvg, fastest}]);
    setScreen('levelpause');
  };

  const beginNextLevel = () => {
    if (isFullRun && level < TOTAL_LEVELS) {
      const nextLvl = level + 1;
      setLevel(nextLvl);
      setScore(0);
      setLastTapTime(0); // RESET
      setTargets([]); // FIX: clear any leftover targets
      setLevelStats({ hits: 0, misses: 0, hitTimes: [], fastest: 9999 });
      spawnedCountRef.current = 0;
      levelEndingRef.current = false; // FIX: allow the new level to end
      setScreen('game');
      setTimeout(() => spawnTarget(nextLvl), 500);
    } else {
      if(isFullRun) finishGame();
      else setScreen('menu');
    }
  };

  const replayLevel = () => {
    setScore(0);
    setLastTapTime(0); // RESET
    setTargets([]); // FIX: clear any leftover targets
    setLevelStats({ hits: 0, misses: 0, hitTimes: [], fastest: 9999 });
    spawnedCountRef.current = 0;
    levelEndingRef.current = false; // FIX: allow the replay to end
    setScreen('game');
    setTimeout(() => spawnTarget(level), 500);
  }

  const finishGame = async () => {
    const overallTotalAvg = Math.round(allLevelStats.reduce((a,b) => a+b.totalAvg,0)/allLevelStats.length);
    const totalHits = allLevelStats.reduce((a,b) => a+b.hits,0);
    const newEntry = { name: playerName, score: totalHits, avg: overallTotalAvg, date: Date.now() };
    const newGlobalLB = [...globalLeaderboard, newEntry].sort((a,b) => b.score - a.score || a.avg - b.avg).slice(0, 10);
    setGlobalLeaderboard(newGlobalLB);
    await AsyncStorage.setItem(GLOBAL_LEADERBOARD_KEY, JSON.stringify(newGlobalLB));
    setScreen('results');
  };

  const startGame = (selectedLevel = 1, fullRun = true) => {
    setIsFullRun(fullRun);
    setLevel(selectedLevel);
    setScore(0);
    setLastTapTime(0); // RESET
    setTargets([]);
    setLevelStats({ hits: 0, misses: 0, hitTimes: [], fastest: 9999 });
    spawnedCountRef.current = 0;
    levelEndingRef.current = false; // FIX: allow this level to end
    if(fullRun) setAllLevelStats([]);
    setScreen('game');
    setTimeout(() => spawnTarget(selectedLevel), 500); // FIX: give the game screen a beat to mount
  };

  const loadLeaderboards = async () => {
    const levelData = await AsyncStorage.getItem(LEVEL_LEADERBOARD_KEY);
    const globalData = await AsyncStorage.getItem(GLOBAL_LEADERBOARD_KEY);
    if (levelData) setLevelLeaderboards(JSON.parse(levelData));
    if (globalData) setGlobalLeaderboard(JSON.parse(globalData));
  };

  const currentAvg = levelStats.hitTimes.length ? Math.round(levelStats.hitTimes.reduce((a,b) => a+b,0)/levelStats.hitTimes.length) : 0;

  // SCREENS
  if (screen === 'menu') {
    return (
      <View style={styles.container}>
        <Text style={styles.title}>Reflex Trainer</Text>
        <Text style={styles.subtitle}>Record: {globalFastest === 9999 ? '--' : globalFastest + 'ms'}</Text>
        <TouchableOpacity style={styles.button} onPress={() => startGame(1, true)}><Text style={styles.buttonText}>Start Full Run</Text></TouchableOpacity>
        <TouchableOpacity style={[styles.button, {backgroundColor:'#0088ff'}]} onPress={() => setScreen('levelselect')}><Text style={styles.buttonText}>Choose Level</Text></TouchableOpacity>
        <TouchableOpacity style={[styles.button, {backgroundColor:'#444'}]} onPress={() => setScreen('leaderboard')}><Text style={styles.buttonText}>Global Ranking</Text></TouchableOpacity>
      </View>
    );
  }

  if (screen === 'levelselect') {
    return (
      <ScrollView style={styles.container}>
        <Text style={styles.title}>Choose Level</Text>
        <View style={styles.grid}>
          {[...Array(TOTAL_LEVELS)].map((_, i) => {
            const lvl = i + 1;
            const speed = (getSpawnInterval(lvl)/1000).toFixed(1);
            return (
              <TouchableOpacity key={lvl} style={styles.levelButton} onPress={() => startGame(lvl, false)}>
                <Text style={styles.levelButtonText}>Lv {lvl}</Text>
                <Text style={{color:'#aaa', fontSize:12}}>{speed}s</Text>
              </TouchableOpacity>
            )
          })}
        </View>
        <TouchableOpacity style={[styles.button, {backgroundColor:'#444'}]} onPress={() => setScreen('menu')}><Text style={styles.buttonText}>Back</Text></TouchableOpacity>
      </ScrollView>
    );
  }

  if (screen === 'levelpause') {
    const lb = levelLeaderboards[level] || [];
    const lastStats = allLevelStats[allLevelStats.length-1];
    const isLastLevel = isFullRun && level >= TOTAL_LEVELS;
    return (
      <View style={styles.container}>
        <Text style={styles.title}>{isLastLevel ? 'Run Complete!' : `Level ${level} Complete!`}</Text>
        <View style={styles.statsBox}>
          <Text style={styles.statLine}>Hit: <Text style={{color:'#00ff88'}}>{lastStats.hits}</Text> | Missed: <Text style={{color:'#ff0088'}}>{lastStats.misses}</Text></Text>
          <Text style={styles.statLine}>Avg Hit Time: {lastStats.avgHit === 9999 ? '--' : lastStats.avgHit + 'ms'}</Text>
          <Text style={styles.statLine}>Fastest This Level: {lastStats.fastest === 9999 ? '--' : lastStats.fastest + 'ms'}</Text>
          <Text style={styles.statLine}>Total Avg: {lastStats.totalAvg}ms</Text>
          <Text style={styles.statLine}>World Rank: {currentLevelRank ? '#' + currentLevelRank : '--'}</Text>
        </View>
        <Text style={{color:'#00ff88', fontSize:18, marginTop:10, marginBottom:10}}>Top 5 on Level {level}</Text>
        {lb.slice(0,5).map((entry, i) => (
          <View key={i} style={styles.leaderRow}>
            <Text style={styles.leaderText}>#{i+1} {entry.name}</Text>
            <Text style={styles.leaderText}>{entry.avg}ms</Text>
            <Text style={styles.leaderText}>{entry.hits}/{entry.hits+entry.misses}</Text>
          </View>
        ))}
        <TouchableOpacity style={[styles.button, {backgroundColor:'#ffaa00'}]} onPress={replayLevel}><Text style={styles.buttonText}>Replay Level {level}</Text></TouchableOpacity>
        {isFullRun && !isLastLevel && <TouchableOpacity style={styles.button} onPress={beginNextLevel}><Text style={styles.buttonText}>Begin Next</Text></TouchableOpacity>}
        {isLastLevel && <TouchableOpacity style={styles.button} onPress={finishGame}><Text style={styles.buttonText}>See Final Results</Text></TouchableOpacity>}
        {!isFullRun && <TouchableOpacity style={styles.button} onPress={() => setScreen('levelselect')}><Text style={styles.buttonText}>Choose Another Level</Text></TouchableOpacity>}
        <TouchableOpacity style={[styles.button, {backgroundColor:'#444'}]} onPress={() => setScreen('menu')}><Text style={styles.buttonText}>Quit to Menu</Text></TouchableOpacity>
      </View>
    );
  }

  if (screen === 'leaderboard') {
    return (
      <ScrollView style={styles.container}>
        <Text style={styles.title}>Global Top 10</Text>
        {globalLeaderboard.map((entry, i) => (
          <View key={i} style={styles.leaderRow}><Text style={styles.leaderText}>#{i+1} {entry.name}</Text><Text style={styles.leaderText}>{entry.score} hits</Text><Text style={styles.leaderText}>{entry.avg}ms</Text></View>
        ))}
        <TouchableOpacity style={styles.button} onPress={() => setScreen('menu')}><Text style={styles.buttonText}>Back</Text></TouchableOpacity>
      </ScrollView>
    );
  }

  if (screen === 'results') {
    const totalHits = allLevelStats.reduce((a,b) => a+b.hits,0);
    const bestFastest = Math.min(...allLevelStats.map(s => s.fastest));
    return (
      <ScrollView style={styles.container}>
        <Text style={styles.title}>Run Complete!</Text>
        <Text style={styles.highscore}>Total Hits: {totalHits}/100</Text>
        <Text style={styles.subtitle}>Best Reaction: {bestFastest === 9999 ? '--' : bestFastest + 'ms'} | Overall Avg: {Math.round(allLevelStats.reduce((a,b) => a+b.totalAvg,0)/allLevelStats.length)}ms</Text>
        {allLevelStats.map(l => (
          <Text key={l.level} style={styles.avgText}>Lv{l.level}: {l.hits}H/{l.misses}M | Fast:{l.fastest === 9999 ? '--' : l.fastest + 'ms'} | TotalAvg:{l.totalAvg}ms</Text>
        ))}
        <TouchableOpacity style={styles.button} onPress={() => startGame(1, true)}><Text style={styles.buttonText}>Play Again</Text></TouchableOpacity>
      </ScrollView>
    );
  }

  // GAME SCREEN
  return (
    <View style={styles.container}>
      <View style={styles.hud}>
        <Text style={styles.hudText}>Lv: {level}/10</Text>
        <Text style={styles.hudText}>{score}/10</Text>
        <Text style={styles.hudText}>{currentAvg}ms</Text>
      </View>
      <Text style={styles.avgText}>Fastest: {levelStats.fastest === 9999 ? '--' : levelStats.fastest + 'ms'} | Last: {lastTapTime}ms | Record: {globalFastest === 9999 ? '--' : globalFastest + 'ms'}</Text>
      <Text style={styles.avgText}>Spawned: {spawnedCountRef.current}/{TARGETS_PER_LEVEL} | Speed: {(getSpawnInterval(level)/1000).toFixed(1)}s</Text>
      {targets.map(target => (
        <TouchableOpacity key={target.id} onPress={() => handleTap(target)} style={[styles.target, { left: target.x, top: target.y, width: target.size, height: target.size, borderRadius: target.size/2 }]}/>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0a0a0a', paddingTop: 60 },
  hud: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 20, marginBottom: 10 },
  hudText: { color: 'white', fontSize: 18, fontWeight: '600' },
  avgText: { color: '#aaa', textAlign: 'center', fontSize: 14, marginBottom: 5 },
  title: { color: 'white', fontSize: 32, fontWeight: 'bold', textAlign: 'center', marginBottom: 10 },
  subtitle: { color: '#00ff88', fontSize: 18, textAlign: 'center', marginBottom: 20 },
  highscore: { color: '#00ff88', fontSize: 24, textAlign: 'center', marginBottom: 10 },
  statsBox: { backgroundColor: '#111', margin: 20, padding: 15, borderRadius: 12, borderWidth: 1, borderColor: '#333' },
  statLine: { color: 'white', fontSize: 18, textAlign: 'center', marginVertical: 4 },
  target: { position: 'absolute', backgroundColor: '#00ff88', shadowColor: '#00ff88', shadowOpacity: 0.6, shadowRadius: 10 },
  button: { backgroundColor: '#00ff88', paddingVertical: 16, paddingHorizontal: 40, borderRadius: 14, margin: 10, alignSelf: 'center', width: '80%' },
  buttonText: { fontSize: 18, fontWeight: 'bold', color: '#000', textAlign: 'center' },
  leaderRow: { flexDirection: 'row', justifyContent: 'space-between', padding: 12, marginHorizontal: 20, borderBottomWidth: 1, borderColor: '#333' },
  leaderText: { color: 'white', fontSize: 16 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', paddingHorizontal: 20 },
  levelButton: { backgroundColor: '#222', padding: 20, borderRadius: 12, margin: 8, width: '28%', alignItems: 'center', borderWidth: 2, borderColor: '#00ff88' },
  levelButtonText: { color: 'white', fontSize: 18, fontWeight: 'bold' }
});
