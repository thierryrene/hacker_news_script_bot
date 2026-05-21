import { execFileSync } from 'child_process';
import path from 'path';
import crypto from 'crypto';

const helperPath = path.resolve('./cache_helper.py');

function runHelper(args) {
  try {
    const stdout = execFileSync('python3', [helperPath, ...args], { encoding: 'utf8' });
    return JSON.parse(stdout.trim());
  } catch (err) {
    console.error(`[Cache Error] Failed running python cache helper with args [${args.join(', ')}]:`, err.message);
    return null;
  }
}

export async function initDb() {
  runHelper(['init']);
}

export function getHash(text) {
  return crypto.createHash('md5').update(text || '').digest('hex');
}

export async function getPostSummary(postId, textHash) {
  const resp = runHelper(['get_post', postId.toString(), textHash]);
  return resp ? resp.result : null;
}

export async function savePostSummary(postId, title, url, textHash, summaryObj) {
  runHelper([
    'save_post',
    postId.toString(),
    title || '',
    url || '',
    textHash,
    summaryObj.emoji || '📰',
    summaryObj.tldr || '',
    summaryObj.porQueImporta || '',
    JSON.stringify(summaryObj.tags || [])
  ]);
}

export async function getCommentSummary(postId, commentsHash) {
  const resp = runHelper(['get_comment', postId.toString(), commentsHash]);
  return resp ? resp.result : null;
}

export async function saveCommentSummary(postId, commentsHash, summaryText) {
  runHelper(['save_comment', postId.toString(), commentsHash, summaryText || '']);
}
