export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center text-center">
      <h1 className="text-7xl font-extrabold text-gray-300">404</h1>
      <p className="mt-2 text-gray-500">Page not found</p>
      <a href="/" className="mt-6 text-sm font-medium text-blue-600 hover:underline">
        Back to Home
      </a>
    </div>
  );
}
