import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { isAxiosError } from 'axios';
import { useAuth } from '../hooks/useAuth';
import type { UserRole } from '@/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';
import { User, Lock } from 'lucide-react';

const loginRoles = [
  { value: 'JOB_SEEKER', label: '求职者', description: '查岗位、看匹配度' },
  { value: 'HR', label: '招聘方（面试官）', description: '管理岗位、筛选简历' },
] as const;

export default function Login() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole | ''>('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  if (isAuthenticated) return <Navigate to="/" replace />;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!role) {
      setError('请选择登录身份。');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await login({ username, password, role });
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const response = isAxiosError<{ detail?: unknown }>(err) ? err.response : undefined;
      const detail = response?.data?.detail;
      if (response?.status === 401) {
        setError('用户名或密码错误，请重试。');
      } else {
        setError(typeof detail === 'string' ? detail : '登录失败，请重试。');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-primary/20 via-background to-primary/10 px-4">
      {/* 抽象几何装饰元素 */}
      <div className="absolute -top-24 -right-24 h-72 w-72 animate-blob rounded-full bg-primary/20 blur-3xl" />
      <div className="absolute -bottom-24 -left-24 h-80 w-80 animate-blob rounded-full bg-primary/10 blur-3xl [animation-delay:2s]" />
      <div className="absolute top-1/3 -left-12 h-48 w-48 animate-blob rounded-full bg-primary/5 blur-3xl [animation-delay:4s]" />
      <div className="absolute bottom-1/4 right-1/4 h-36 w-36 animate-blob rounded-full bg-primary/15 blur-3xl [animation-delay:1s]" />

      <Card className="w-full max-w-sm animate-fade-in bg-white/70 backdrop-blur-xl dark:bg-black/50">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">招聘与求职辅助系统</CardTitle>
          <CardDescription>选择登录身份，再输入账号和密码</CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <div role="alert" className="mb-4 rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <fieldset disabled={loading}>
              <legend className="mb-2 text-sm font-medium">登录身份</legend>
              <div className="grid grid-cols-2 gap-2">
                {loginRoles.map((option) => (
                  <label key={option.value} className="flex cursor-pointer items-start gap-2 rounded-lg border border-border p-2.5 text-sm has-checked:border-primary has-checked:bg-primary/5">
                    <input
                      type="radio"
                      name="role"
                      value={option.value}
                      checked={role === option.value}
                      onChange={() => {
                        setRole(option.value);
                        setError('');
                      }}
                      className="mt-0.5 size-4 shrink-0 accent-primary"
                      required
                    />
                    <span>
                      <span className="block font-medium">{option.label}</span>
                      <span className="mt-0.5 block text-xs text-muted-foreground">{option.description}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="flex flex-col gap-2">
              <label htmlFor="username" className="text-sm font-medium">用户名</label>
              <div className="relative">
                <User className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="username"
                  type="text"
                  placeholder="请输入用户名"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="pl-8"
                  required
                />
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <label htmlFor="password" className="text-sm font-medium">密码</label>
              <div className="relative">
                <Lock className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="password"
                  type="password"
                  placeholder="请输入密码"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-8"
                  required
                />
              </div>
            </div>

            <Button type="submit" disabled={loading} className="w-full">
              {loading && <Spinner data-icon="inline-start" />}
              {loading ? '登录中...' : '登录'}
            </Button>
          </form>

          <p className="text-center text-sm text-muted-foreground mt-4">
            还没有账号？{' '}
            <Link to="/register" className="text-primary underline-offset-4 hover:underline">
              立即注册
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
