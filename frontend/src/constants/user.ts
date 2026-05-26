/** 当前登录用户展示信息（Demo；后续可接 SSO / 接口） */
export const CURRENT_USER = {
  username: (import.meta.env.VITE_APP_USERNAME as string | undefined) ?? 'wangjb',
  displayName: (import.meta.env.VITE_APP_DISPLAY_NAME as string | undefined) ?? 'wangjb',
}

export function userAvatarText(name: string): string {
  const t = name.trim()
  if (!t) return '?'
  return t.charAt(0).toUpperCase()
}
